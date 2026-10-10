from __future__ import annotations

from django.apps.registry import apps as global_apps
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, ProgrammingError, connection, router
from django.db.migrations import (
    AddConstraint,
    AddField,
    AddIndex,
    AlterField,
    CreateModel,
    DeleteModel,
    RemoveConstraint,
    RemoveField,
    RemoveIndex,
    RenameField,
    RenameModel,
    RunPython,
    RunSQL,
    SeparateDatabaseAndState,
)
from django.db.migrations.executor import MigrationExecutor

# SQLSTATEs that mean "the object we want to create is already there":
# 42701 duplicate_column, 42710 duplicate_object,
# 42P06 duplicate_schema, 42P07 duplicate_table.
DUPLICATE_SQLSTATES = frozenset({"42701", "42710", "42P06", "42P07"})


def _is_duplicate_error(exc: BaseException) -> bool:
    cause = getattr(exc, "__cause__", None)
    sqlstate = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    if sqlstate in DUPLICATE_SQLSTATES:
        return True
    return "already exists" in " ".join(str(exc).split()).lower()


class _Retry(Exception):
    """Internal signal: the object an operation creates is already there."""


class SchemaSnapshot:
    """A read-only view of the objects that really exist in the database."""

    def __init__(self, connection):
        self.connection = connection
        self._tables: set[str] | None = None
        self._columns: dict[str, set[str]] = {}
        self._objects: set[str] | None = None

    @property
    def tables(self) -> set[str]:
        if self._tables is None:
            with self.connection.cursor() as cursor:
                self._tables = set(self.connection.introspection.table_names(cursor))
        return self._tables

    def has_table(self, name: str | None) -> bool:
        return bool(name) and name in self.tables

    def has_column(self, table: str | None, column: str | None) -> bool:
        if not table or not column or table not in self.tables:
            return False
        if table not in self._columns:
            with self.connection.cursor() as cursor:
                try:
                    description = self.connection.introspection.get_table_description(
                        cursor, table
                    )
                except Exception:  # pragma: no cover - defensive
                    description = []
            self._columns[table] = {column.name for column in description}
        return column in self._columns[table]

    @property
    def object_names(self) -> set[str]:
        """Names of every index and constraint in the database."""
        if self._objects is None:
            names: set[str] = set()
            with self.connection.cursor() as cursor:
                for table in sorted(self.tables):
                    try:
                        names.update(
                            self.connection.introspection.get_constraints(cursor, table)
                        )
                    except Exception:  # pragma: no cover - defensive
                        continue
            self._objects = names
        return self._objects

    def has_named_object(self, name: str | None) -> bool:
        return bool(name) and name in self.object_names


def _state_model(state, app_label: str, model_name: str):
    model = state.apps.get_model(app_label, model_name)
    if model._meta.swapped:
        model = global_apps.get_model(model._meta.swapped)
    return model


def _migrated(model, app_label: str) -> bool:
    """Whether Django creates a table for this model at all."""
    if model._meta.proxy or not model._meta.managed:
        return False
    return router.allow_migrate(
        connection.alias, app_label, model_name=model._meta.model_name
    )


def _should_be_altered(old_field, new_field) -> bool:
    """Whether Django would send any SQL to the database for this change."""
    editor = connection.schema_editor()
    checker = getattr(editor, "_field_should_be_altered", None)
    if checker is None:  # pragma: no cover - older/other backends
        return True
    return checker(old_field, new_field)


class Command(BaseCommand):
    help = (
        "Repair a database whose django_migrations table is out of step with the "
        "objects that are really in it. Every pending migration is inspected "
        "operation by operation: the parts that are already in the database are "
        "recorded without being run again, and only the missing parts are applied."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be done without changing the database.",
        )

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.verbosity = options["verbosity"]

        executor = MigrationExecutor(connection, self._progress)
        executor.loader.check_consistent_history(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        pending = [migration for migration, backwards in plan if not backwards]

        if not pending:
            self.stdout.write(
                self.style.SUCCESS(
                    "The database is in step with the migrations on disk; "
                    "there is nothing to repair."
                )
            )
            return

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "%d migration(s) are missing from django_migrations:"
                % len(pending)
            )
        )

        state = executor._create_project_state(with_applied_migrations=True)
        counts = {"recorded": 0, "applied": 0, "partial": 0}

        for migration in pending:
            snapshot = SchemaSnapshot(connection)
            present = self._detect_applied(migration, state, snapshot)
            label = f"{migration.app_label}.{migration.name}"
            total = len(migration.operations)
            missing = total - len(present)

            if not missing:
                counts["recorded"] += 1
                detail = "already in the database"
            elif missing == total:
                counts["applied"] += 1
                detail = "applied now"
            else:
                counts["partial"] += 1
                detail = (
                    "partly in the database: %d operation(s) applied, %d recorded"
                    % (missing, len(present))
                )

            if self.dry_run:
                self.stdout.write(f"  {label}: {detail}")
                state = migration.mutate_state(state)
                continue

            state = self._run(migration, state)
            executor.record_migration(migration)
            self.stdout.write(self.style.SUCCESS(f"  {label}: {detail}"))

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nNothing was changed. Run the command again without "
                    "--dry-run to repair the database."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                "\nDone: %d recorded as already applied, %d applied now, "
                "%d repaired partially."
                % (counts["recorded"], counts["applied"], counts["partial"])
            )
        )
        self.stdout.write("Check the result with: python manage.py migrate")

    def _progress(self, action, migration=None, fake=False):
        if self.verbosity < 2 or migration is None:
            return
        self.stdout.write(f"    {action}: {migration.app_label}.{migration.name}")

    # ------------------------------------------------------------------ detect

    def _detect_applied(self, migration, state, snapshot) -> set[int]:
        """Indices of the operations whose database work is already done."""
        applied: set[int] = set()
        work_state = state.clone()
        for index, operation in enumerate(migration.operations):
            old_state = work_state.clone()
            operation.state_forwards(migration.app_label, work_state)
            if self._operation_applied(
                migration.app_label, operation, old_state, work_state, snapshot
            ):
                applied.add(index)
        return self._settle(migration, applied)

    def _settle(self, migration, applied: set[int]) -> set[int]:
        """
        Decide what to do with the operations that cannot be inspected.

        Data operations (RunPython, RunSQL) leave no trace that can be read
        back. When every structural operation of a migration is already in the
        database the migration has run, so its data operations are recorded
        instead of being run a second time.
        """
        structural = [
            index
            for index, operation in enumerate(migration.operations)
            if not isinstance(operation, (RunPython, RunSQL))
        ]
        if structural and all(index in applied for index in structural):
            return set(range(len(migration.operations)))
        return applied

    def _operation_applied(self, app_label, operation, old_state, new_state, snapshot):
        if isinstance(operation, SeparateDatabaseAndState):
            return not operation.database_operations

        if isinstance(operation, CreateModel):
            model = _state_model(new_state, app_label, operation.name)
            if not _migrated(model, app_label):
                return True
            return snapshot.has_table(model._meta.db_table)

        if isinstance(operation, DeleteModel):
            model = _state_model(old_state, app_label, operation.name)
            if not _migrated(model, app_label):
                return True
            return not snapshot.has_table(model._meta.db_table)

        if isinstance(operation, RenameModel):
            model = _state_model(new_state, app_label, operation.new_name)
            return snapshot.has_table(model._meta.db_table)

        if isinstance(operation, AddField):
            model = _state_model(new_state, app_label, operation.model_name)
            if not _migrated(model, app_label):
                return True
            field = model._meta.get_field(operation.name)
            if field.many_to_many:
                return snapshot.has_table(field.remote_field.through._meta.db_table)
            return snapshot.has_column(model._meta.db_table, field.column)

        if isinstance(operation, RemoveField):
            model = _state_model(old_state, app_label, operation.model_name)
            if not _migrated(model, app_label):
                return True
            field = model._meta.get_field(operation.name)
            if field.many_to_many:
                return not snapshot.has_table(field.remote_field.through._meta.db_table)
            return not snapshot.has_column(model._meta.db_table, field.column)

        if isinstance(operation, RenameField):
            model = _state_model(new_state, app_label, operation.model_name)
            field = model._meta.get_field(operation.new_name)
            return snapshot.has_column(model._meta.db_table, field.column)

        if isinstance(operation, AlterField):
            model = _state_model(new_state, app_label, operation.model_name)
            if not _migrated(model, app_label):
                return True
            try:
                old_field = _state_model(
                    old_state, app_label, operation.model_name
                )._meta.get_field(operation.name)
                new_field = model._meta.get_field(operation.name)
            except FieldDoesNotExist:
                return False
            # Nothing to do when the change never reaches the database, for
            # example a new set of choices or a new verbose name.
            return not _should_be_altered(old_field, new_field)

        if isinstance(operation, AddIndex):
            return snapshot.has_named_object(operation.index.name)

        if isinstance(operation, RemoveIndex):
            return not snapshot.has_named_object(operation.index.name)

        if isinstance(operation, AddConstraint):
            return snapshot.has_named_object(operation.constraint.name)

        if isinstance(operation, RemoveConstraint):
            return not snapshot.has_named_object(operation.constraint.name)

        # RunSQL, RunPython and everything else cannot be inspected, so they
        # are always run (they are written to be safe to re-run).
        return False

    # -------------------------------------------------------------------- apply

    def _run(self, migration, state):
        """Run the operations of *migration* that are not in the database yet."""
        present = self._detect_applied(migration, state, SchemaSnapshot(connection))
        for _attempt in range(len(migration.operations) + 1):
            work_state = state.clone()
            try:
                with connection.schema_editor(atomic=migration.atomic) as editor:
                    for index, operation in enumerate(migration.operations):
                        old_state = work_state.clone()
                        operation.state_forwards(migration.app_label, work_state)
                        if index in present:
                            continue
                        try:
                            operation.database_forwards(
                                migration.app_label, editor, old_state, work_state
                            )
                        except (ProgrammingError, IntegrityError) as exc:
                            if not _is_duplicate_error(exc):
                                raise
                            # The object it wants to create is already there:
                            # roll this attempt back and skip that operation.
                            present.add(index)
                            raise _Retry(str(exc)) from exc
            except _Retry:
                continue
            return work_state

        raise CommandError(
            "Could not repair %s.%s: it keeps reporting objects that already "
            "exist. Inspect the database by hand."
            % (migration.app_label, migration.name)
        )
