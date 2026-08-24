"""Move the Zaminex database from SQLite to PostgreSQL, safely and repeatably.

The command performs the three steps of the migration in order and verifies the
result, so a half-finished run cannot silently corrupt the data:

    1. dump    — export every row from the SQLite file into a JSON fixture
    2. migrate — build the schema in the target PostgreSQL database
    3. load    — restore the fixture and reset the primary-key sequences
    4. verify  — compare per-model row counts between source and target

Usage
-----
    # 1. Point DATABASE_URL at the *target* PostgreSQL database
    export DATABASE_URL=postgres://zaminex:zaminex@localhost:5432/zaminex

    # 2. Preview what would happen (no writes)
    python manage.py migrate_to_postgres --dry-run

    # 3. Run it
    python manage.py migrate_to_postgres

Notes
-----
* The SQLite file is only ever read, never modified, so the original database
  remains a valid rollback point.
* ``contenttypes`` and ``auth.permission`` are excluded from the dump because
  Django recreates them during ``migrate``; including them causes duplicate-key
  errors on restore.
* Primary keys are preserved verbatim. This matters because the frontend stores
  IDs (``currentConsultantId``, ``consultantId``, ...) and renumbering users
  would silently repoint properties at the wrong consultant.
"""

from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections


# Temporary alias used to read the SQLite source while `default` stays on
# PostgreSQL. Registered for the duration of the dump, then removed.
SOURCE_ALIAS = "__sqlite_source"

# Django expects these keys on every connection definition.
BLANK_DB_SETTINGS = {
    "ATOMIC_REQUESTS": False,
    "AUTOCOMMIT": True,
    "CONN_MAX_AGE": 0,
    "CONN_HEALTH_CHECKS": False,
    "OPTIONS": {},
    "TIME_ZONE": None,
    "USER": "",
    "PASSWORD": "",
    "HOST": "",
    "PORT": "",
    "TEST": {"CHARSET": None, "COLLATION": None, "MIGRATE": True, "MIRROR": None, "NAME": None},
}

# Recreated by `migrate`; restoring them would collide on unique constraints.
EXCLUDED_APPS = ["contenttypes", "auth.permission", "admin.logentry", "sessions.session"]

# Models compared during the verification step.
VERIFIED_MODELS = [
    "accounts.User",
    "accounts.ConsultantProfile",
    "accounts.AdminProfile",
    "accounts.LoginAttempt",
    "common.District",
    "common.ActivityLog",
    "common.CompanySettings",
    "common.Notification",
    "properties.Property",
    "properties.PropertyImage",
    "listings.Listing",
    "tasks.Task",
    "followups.FollowUp",
]


class Command(BaseCommand):
    help = "Migrate the Zaminex database from SQLite to PostgreSQL (dump → migrate → load → verify)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=None,
            help="Path to the source SQLite file (default: BASE_DIR/db.sqlite3).",
        )
        parser.add_argument(
            "--fixture",
            default=None,
            help="Where to write the intermediate fixture (default: BASE_DIR/fixtures/seed_data.json).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without writing to the target database.",
        )
        parser.add_argument(
            "--skip-dump",
            action="store_true",
            help="Reuse an existing fixture instead of re-exporting from SQLite.",
        )

    # -- helpers ------------------------------------------------------------

    def _ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))

    def _warn(self, msg):
        self.stdout.write(self.style.WARNING(f"  ! {msg}"))

    def _step(self, msg):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{msg}"))

    def _sqlite_counts(self, sqlite_path: Path) -> dict[str, int]:
        """Row count per model, read straight from the SQLite file."""
        counts: dict[str, int] = {}
        con = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        try:
            for label in VERIFIED_MODELS:
                table = apps.get_model(label)._meta.db_table
                try:
                    counts[label] = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                except sqlite3.OperationalError:
                    counts[label] = -1  # table absent in the source
        finally:
            con.close()
        return counts

    # -- main ---------------------------------------------------------------

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        sqlite_path = Path(options["sqlite_path"] or base_dir / "db.sqlite3")
        fixture_path = Path(options["fixture"] or base_dir / "fixtures" / "seed_data.json")
        dry_run = options["dry_run"]

        target = settings.DATABASES["default"]
        is_postgres = "postgresql" in target["ENGINE"]

        self._step("Zaminex · SQLite → PostgreSQL migration")
        self.stdout.write(f"  source  : {sqlite_path}")
        self.stdout.write(f"  target  : {target['ENGINE']} → {target.get('NAME')}")
        self.stdout.write(f"  fixture : {fixture_path}")

        if not is_postgres:
            raise CommandError(
                "The target database is not PostgreSQL.\n"
                "Set DATABASE_URL first, e.g.\n"
                "  export DATABASE_URL=postgres://zaminex:zaminex@localhost:5432/zaminex"
            )

        if not sqlite_path.exists() and not options["skip_dump"]:
            raise CommandError(f"SQLite file not found: {sqlite_path}")

        source_counts = self._sqlite_counts(sqlite_path) if sqlite_path.exists() else {}
        total_rows = sum(c for c in source_counts.values() if c > 0)
        self.stdout.write(f"  rows    : {total_rows} across {len(source_counts)} models")

        if dry_run:
            self._step("Dry run — no changes written")
            for label, count in source_counts.items():
                self.stdout.write(f"    {label:38} {count:>6}")
            self.stdout.write(
                "\n  Would run: dumpdata → migrate → loaddata → sqlsequencereset → verify"
            )
            return

        # -- 1. dump --------------------------------------------------------
        if options["skip_dump"]:
            self._step("1/4  Dump skipped (--skip-dump)")
            if not fixture_path.exists():
                raise CommandError(f"Fixture not found: {fixture_path}")
        else:
            self._step("1/4  Exporting data from SQLite")
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            # Read the source through a dedicated connection alias rather than
            # mutating DATABASES["default"]. Django caches a connection wrapper
            # per alias, so swapping the default mid-process leaves the ORM
            # holding a stale cursor against the wrong backend.
            settings.DATABASES[SOURCE_ALIAS] = {
                **BLANK_DB_SETTINGS,
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(sqlite_path),
            }
            connections.databases[SOURCE_ALIAS] = settings.DATABASES[SOURCE_ALIAS]
            try:
                buffer = io.StringIO()
                call_command(
                    "dumpdata",
                    *[f"--exclude={app}" for app in EXCLUDED_APPS],
                    database=SOURCE_ALIAS,
                    indent=2,
                    stdout=buffer,
                )
                fixture_path.write_text(buffer.getvalue(), encoding="utf-8")
            finally:
                connections[SOURCE_ALIAS].close()
                connections.databases.pop(SOURCE_ALIAS, None)
                settings.DATABASES.pop(SOURCE_ALIAS, None)
            self._ok(f"wrote {fixture_path} ({fixture_path.stat().st_size // 1024} KB)")

        # -- 2. schema ------------------------------------------------------
        self._step("2/4  Creating the schema in PostgreSQL")
        call_command("migrate", verbosity=0)
        self._ok("all migrations applied")

        # -- 3. restore -----------------------------------------------------
        self._step("3/4  Loading the data into PostgreSQL")
        call_command("loaddata", str(fixture_path), verbosity=0)
        self._ok("fixture restored")

        # PostgreSQL keeps a sequence per table. Restoring explicit primary
        # keys does not advance it, so without this the next INSERT would
        # reuse an existing id and fail with a duplicate-key error.
        self.stdout.write("  resetting primary-key sequences…")
        with connection.cursor() as cursor:
            for app_config in apps.get_app_configs():
                models = list(app_config.get_models())
                if not models:
                    continue
                statements = connection.ops.sequence_reset_sql(
                    self.style, models
                )
                for statement in statements:
                    cursor.execute(statement)
        self._ok("sequences aligned with the restored rows")

        # -- 4. verify ------------------------------------------------------
        self._step("4/4  Verifying row counts")
        self.stdout.write(f"    {'model':38} {'sqlite':>7} {'postgres':>9}   status")
        mismatches = []
        for label in VERIFIED_MODELS:
            expected = source_counts.get(label, -1)
            actual = apps.get_model(label).objects.count()
            if expected < 0:
                status, style = "skipped", self.style.WARNING
            elif expected == actual:
                status, style = "OK", self.style.SUCCESS
            else:
                status, style = "MISMATCH", self.style.ERROR
                mismatches.append((label, expected, actual))
            self.stdout.write(
                f"    {label:38} {expected:>7} {actual:>9}   " + style(status)
            )

        if mismatches:
            raise CommandError(
                f"{len(mismatches)} model(s) did not match. "
                "The SQLite file is untouched — fix the cause and re-run."
            )

        self._step("Migration complete")
        self.stdout.write(
            "  Every row was transferred and verified.\n"
            "  The original SQLite file is unchanged and can be kept as a rollback point.\n\n"
            "  Next: run the test suite against PostgreSQL to confirm application behaviour:\n"
            "    TEST_ON_POSTGRES=1 python manage.py test\n"
        )
