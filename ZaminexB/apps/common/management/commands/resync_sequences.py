from __future__ import annotations

import difflib
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction

DEFAULT_SCHEMA = "public"

TABLE_WIDTH = 36
LABEL_WIDTH = 18
NUMBER_WIDTH = 12

_SEQUENCE_COLUMNS_SQL = """
SELECT c.relname, a.attname, n.nspname, s.relname
FROM pg_class c
JOIN pg_namespace cns ON cns.oid = c.relnamespace
JOIN pg_attribute a
  ON a.attrelid = c.oid
 AND a.attnum > 0
 AND NOT a.attisdropped
JOIN pg_index i
  ON i.indrelid = c.oid
 AND i.indisprimary
JOIN pg_depend d
  ON d.refclassid = 'pg_class'::regclass
 AND d.classid = 'pg_class'::regclass
 AND d.refobjid = c.oid
 AND d.refobjsubid = a.attnum
 AND d.deptype IN ('a', 'i')
JOIN pg_class s
  ON s.oid = d.objid
 AND s.relkind = 'S'
JOIN pg_namespace n ON n.oid = s.relnamespace
WHERE c.relkind = 'r'
  AND cns.nspname = %s
  AND a.attnum = ANY (i.indkey)
ORDER BY c.relname, a.attname
"""


def _quote(identifier: str) -> str:
    return connection.ops.quote_name(identifier)


def sequence_columns(schema: str = DEFAULT_SCHEMA):
    with connection.cursor() as cursor:
        cursor.execute(_SEQUENCE_COLUMNS_SQL, [schema])
        rows = cursor.fetchall()
    return [(row[0], row[1], row[2], row[3]) for row in rows]


def schema_exists(schema: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", [schema])
        return cursor.fetchone() is not None


def has_tables(schema: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE' LIMIT 1",
            [schema],
        )
        return cursor.fetchone() is not None


def read_sequence(sequence_schema: str, sequence_name: str) -> tuple[int, bool]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT last_value, is_called FROM "
            f"{_quote(sequence_schema)}.{_quote(sequence_name)}"
        )
        last_value, is_called = cursor.fetchone()
    return int(last_value), bool(is_called)


def read_max_id(table: str, column: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COALESCE(MAX({_quote(column)}), 0) FROM {_quote(table)}"
        )
        return int(cursor.fetchone()[0] or 0)


def next_id_for(last_value: int, is_called: bool) -> int:
    return last_value + 1 if is_called else last_value


def resync_sequence(
    table: str, column: str, sequence_schema: str, sequence_name: str
) -> int:
    sequence = f"{_quote(sequence_schema)}.{_quote(sequence_name)}"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT setval(%s::regclass, "
            f"COALESCE(MAX({_quote(column)}), 1), "
            f"MAX({_quote(column)}) IS NOT NULL) "
            f"FROM {_quote(table)}",
            [sequence],
        )
    last_value, is_called = read_sequence(sequence_schema, sequence_name)
    return next_id_for(last_value, is_called)


class Command(BaseCommand):
    help = (
        "Check every auto-incrementing primary key and move the ones that fell "
        "behind their table's highest id, so the next INSERT cannot collide "
        "(the usual cause of 'duplicate key value violates unique constraint "
        '"<table>_pkey"\').'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Only report; change nothing. Exits with status 1 when a "
                "sequence is behind its data, so it can be used as a check."
            ),
        )
        parser.add_argument(
            "--table",
            action="append",
            default=[],
            metavar="NAME",
            help=(
                "Limit the run to one table (repeat the option for several). "
                "Defaults to every table of the schema."
            ),
        )
        parser.add_argument(
            "--schema",
            default=DEFAULT_SCHEMA,
            help=f"Database schema to inspect (default: {DEFAULT_SCHEMA}).",
        )

    def _head(self, message: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{message}"))

    def _fact(self, label: str, value, style=None) -> None:
        text = f"  {label.ljust(LABEL_WIDTH)}: {value}"
        self.stdout.write(style(text) if style else text)

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError(
                "Zaminex stores its data in PostgreSQL, but this connection "
                f"uses '{connection.vendor}'. Point the project at its "
                "PostgreSQL database and run the command again."
            )

        dry_run = options["dry_run"]
        schema = options["schema"]
        verbosity = options["verbosity"]

        try:
            columns = sequence_columns(schema)
        except DatabaseError as exc:
            raise CommandError(
                f"Could not read schema '{schema}' from the database: {exc}"
            ) from exc

        if not columns:
            database = connection.settings_dict.get("NAME") or "this database"
            try:
                if not schema_exists(schema):
                    raise CommandError(
                        f"Schema '{schema}' does not exist in {database}. "
                        "Check the --schema value."
                    )
                if not has_tables(schema):
                    raise CommandError(
                        f"Schema '{schema}' has no tables yet. Restore your "
                        "backup (psql -v ON_ERROR_STOP=1 -f zaminex_backup.sql) "
                        "or run 'python manage.py migrate' first, then run this "
                        "command again."
                    )
            except DatabaseError as exc:
                raise CommandError(
                    f"Could not read schema '{schema}' from the database: {exc}"
                ) from exc

            raise CommandError(
                "No table with an auto-incrementing primary key was found in "
                f"schema '{schema}'. Check the --schema value."
            )

        wanted = {name.strip() for name in options["table"] if name.strip()}
        if wanted:
            known = {table for table, *_ in columns}
            missing = sorted(wanted - known)
            if missing:
                suggestions = difflib.get_close_matches(
                    missing[0], sorted(known), n=3, cutoff=0.5
                )
                hint = (
                    f" Did you mean {', '.join(suggestions)}?" if suggestions else ""
                )
                raise CommandError(
                    f"Table '{missing[0]}' has no auto-incrementing primary key "
                    f"in schema '{schema}'.{hint}"
                )
            columns = [row for row in columns if row[0] in wanted]

        self._head("بررسی دنباله‌های شماره‌گذاری (resync_sequences)")
        self._fact("پایگاه داده", connection.settings_dict.get("NAME") or "—")
        self._fact("اسکیما", schema)
        self._fact(
            "حالت",
            "بررسی (--dry-run) — هیچ تغییری اعمال نمی‌شود"
            if dry_run
            else "اصلاح — دنباله‌های عقب‌مانده جابه‌جا می‌شوند",
        )

        healthy: list[tuple[str, int, int]] = []
        repaired: list[tuple[str, int, int, int]] = []
        behind: list[tuple[str, int, int]] = []
        failed: list[tuple[str, str]] = []

        for table, column, sequence_schema, sequence_name in columns:
            try:
                with transaction.atomic():
                    last_value, is_called = read_sequence(
                        sequence_schema, sequence_name
                    )
                    max_id = read_max_id(table, column)
                    current_next = next_id_for(last_value, is_called)

                    if current_next > max_id:
                        healthy.append((table, current_next, max_id))
                        continue

                    if dry_run:
                        behind.append((table, current_next, max_id))
                        continue

                    new_next = resync_sequence(
                        table, column, sequence_schema, sequence_name
                    )
                    repaired.append((table, current_next, max_id, new_next))
            except DatabaseError as exc:
                failed.append((table, " ".join(str(exc).split())))

        problem_rows = [
            (table, next_id, "", max_id, "BEHIND")
            for table, next_id, max_id in behind
        ] + [
            (table, before, str(after), max_id, "FIXED")
            for table, before, max_id, after in repaired
        ]

        if problem_rows:
            self._head(
                f"{len(problem_rows)} دنباله با دادهٔ جدولش تلاقی می‌کند:"
            )
            self.stdout.write(
                f"  {'table'.ljust(TABLE_WIDTH)} {'next id':>{NUMBER_WIDTH}} "
                f"{'max id':>{NUMBER_WIDTH}}   status"
            )
            for table, next_id, after, max_id, status in problem_rows:
                next_column = f"{next_id} → {after}" if after else str(next_id)
                self.stdout.write(
                    f"  {table.ljust(TABLE_WIDTH)} {next_column:>{NUMBER_WIDTH}} "
                    f"{max_id:>{NUMBER_WIDTH}}   {status}"
                )
            self.stdout.write("")
            if behind:
                self.stdout.write(
                    "  BEHIND : شناسهٔ بعدی این دنباله با یکی از ردیف‌های موجود "
                    "تلاقی می‌کند."
                )
            if repaired:
                self.stdout.write(
                    "  FIXED  : دنباله به بیشینهٔ جدول منتقل شد؛ شناسهٔ بعدی "
                    "حالا max + 1 است."
                )

        if verbosity >= 2 and healthy:
            self._head(f"{len(healthy)} دنباله سالم (بدون تلاقی):")
            self.stdout.write(
                f"  {'table'.ljust(TABLE_WIDTH)} {'next id':>{NUMBER_WIDTH}} "
                f"{'max id':>{NUMBER_WIDTH}}"
            )
            for table, next_id, max_id in healthy:
                self.stdout.write(
                    f"  {table.ljust(TABLE_WIDTH)} {next_id:>{NUMBER_WIDTH}} "
                    f"{max_id:>{NUMBER_WIDTH}}"
                )

        self._head("خلاصه")
        self._fact("جدول‌های بررسی‌شده", len(columns))
        self._fact("سالم", len(healthy))
        self._fact("عقب‌مانده", len(behind) + len(repaired))
        if not dry_run:
            self._fact("اصلاح‌شده", len(repaired))
        if failed:
            self._fact("ناموفق", len(failed))

        self.stdout.write("")
        if failed:
            for table, message in failed:
                self.stdout.write(self.style.ERROR(f"  ✗ {table}: {message}"))
            raise CommandError(
                f"{len(failed)} table(s) could not be checked. See the messages "
                "above; the tables that did work were left consistent."
            )

        if dry_run and behind:
            self.stdout.write(
                self.style.WARNING(
                    f"  {len(behind)} دنباله از داده عقب است. همین دستور را "
                    "بدون --dry-run اجرا کنید تا اصلاح شوند."
                )
            )
            sys.exit(1)

        if repaired:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {len(repaired)} دنباله اصلاح شد؛ شناسهٔ بعدی هر جدول "
                    "حالا بعد از بزرگ‌ترین شناسهٔ موجود می‌آید."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  هر {len(columns)} دنباله با دادهٔ جدولش هماهنگ است — "
                    "کاری برای انجام نمانده."
                )
            )
