from unittest.mock import patch

from django.db import connection
from django.test import TestCase

from apps.common.checks import check_pending_migrations


class PendingMigrationsCheckTests(TestCase):
    def test_silent_when_the_database_is_current(self):
        self.assertEqual(check_pending_migrations(None), [])

    def test_warns_when_a_recorded_migration_is_removed(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM django_migrations WHERE app = 'tickets' AND name LIKE %s",
                ["0004%"],
            )

        issues = check_pending_migrations(None)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, "migrations.W001")
        self.assertIn("tickets.0004", issues[0].msg)
        self.assertEqual(issues[0].hint, "python manage.py migrate")

    def test_reports_the_count_and_truncates_the_list(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM django_migrations WHERE app IN ('tickets', 'tasks', 'followups')"
            )
            deleted = cursor.rowcount
        self.assertGreater(deleted, 5, "fixture needs >5 to exercise truncation")

        message = check_pending_migrations(None)[0].msg
        self.assertIn(f"missing {deleted} migration(s)", message)
        self.assertIn("and", message)
        self.assertIn("more", message)

    def test_is_silent_when_the_database_cannot_be_reached(self):
        class _NoDatabase:
            def cursor(self):
                raise Exception("connection refused")

            def __getattr__(self, name):
                raise Exception("connection refused")

        with patch("django.db.connection", _NoDatabase()):
            self.assertEqual(check_pending_migrations(None), [])

    def test_is_a_warning_not_an_error(self):
        from django.core.checks import Warning as CheckWarning

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM django_migrations WHERE app = 'tickets' AND name LIKE %s",
                ["0004%"],
            )
        self.assertIsInstance(check_pending_migrations(None)[0], CheckWarning)
