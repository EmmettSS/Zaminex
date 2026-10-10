from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import ProgrammingError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase

from apps.common.management.commands.repair_migrations import (
    Command,
    _is_duplicate_error,
)

ACCOUNTS_0011 = "0011_loginsettings_smslogincode_smsprovidersettings"


def run_command(*args):
    out = StringIO()
    call_command("repair_migrations", *args, stdout=out)
    return out.getvalue()


def is_recorded(app_label, name):
    return (app_label, name) in MigrationExecutor(connection).loader.applied_migrations


def forget(app_label, name):
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM django_migrations WHERE app = %s AND name = %s",
            [app_label, name],
        )


def table_exists(name):
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s)", [name])
        return cursor.fetchone()[0] is not None


class RepairMigrationsTests(TestCase):
    def test_says_so_when_the_database_is_in_step(self):
        output = run_command()

        self.assertIn("nothing to repair", output)

    def test_dry_run_records_nothing(self):
        forget("accounts", ACCOUNTS_0011)

        output = run_command("--dry-run")

        self.assertIn(ACCOUNTS_0011, output)
        self.assertFalse(is_recorded("accounts", ACCOUNTS_0011))

    def test_records_a_migration_that_is_already_in_the_database(self):
        forget("accounts", ACCOUNTS_0011)

        run_command()

        self.assertTrue(is_recorded("accounts", ACCOUNTS_0011))
        self.assertTrue(table_exists("accounts_loginsettings"))
        self.assertTrue(table_exists("accounts_smslogincode"))
        self.assertTrue(table_exists("accounts_smsprovidersettings"))

    def test_applies_only_the_parts_that_are_missing(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE accounts_smslogincode")
        forget("accounts", ACCOUNTS_0011)

        run_command()

        self.assertTrue(is_recorded("accounts", ACCOUNTS_0011))
        self.assertTrue(table_exists("accounts_smslogincode"))

    def test_records_a_migration_that_holds_no_database_work(self):
        forget("common", "0015_remove_notification")

        run_command()

        self.assertTrue(is_recorded("common", "0015_remove_notification"))

    def test_keeps_going_when_detection_misses_an_object(self):
        forget("accounts", ACCOUNTS_0011)

        with patch.object(Command, "_detect_applied", return_value=set()):
            run_command()

        self.assertTrue(is_recorded("accounts", ACCOUNTS_0011))
        self.assertTrue(table_exists("accounts_smslogincode"))

    def test_recognises_duplicate_object_errors(self):
        duplicate = ProgrammingError('relation "accounts_loginsettings" already exists')
        duplicate.__cause__ = type("Cause", (Exception,), {"pgcode": "42P07"})()

        self.assertTrue(_is_duplicate_error(duplicate))
        self.assertFalse(_is_duplicate_error(ProgrammingError("syntax error")))
