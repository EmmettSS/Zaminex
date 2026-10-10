import sys
from unittest.mock import patch

from django.core.checks import Error
from django.core.checks import Warning as CheckWarning
from django.db import OperationalError
from django.test import TestCase

from apps.common import checks
from apps.common.checks import (
    check_database_reachable,
    check_pending_migrations,
    check_pg_trgm,
)

REFUSED = (
    'connection to server at "localhost" (::1), port 5432 failed: '
    "Connection refused"
)

SERVER = {
    "HOST": "localhost",
    "PORT": "5432",
    "NAME": "zaminex",
    "USER": "zaminex",
    "OPTIONS": {"connect_timeout": 5},
}


class _DeadConnection:
    vendor = "postgresql"

    def __init__(self, settings_dict=None):
        self.settings_dict = dict(SERVER if settings_dict is None else settings_dict)
        self.attempts = 0

    def ensure_connection(self):
        self.attempts += 1
        raise OperationalError(REFUSED)

    def cursor(self):
        raise OperationalError(REFUSED)

    def __getattr__(self, name):
        raise OperationalError(REFUSED)


class _LiveConnection:
    vendor = "postgresql"

    def __init__(self):
        self.settings_dict = dict(SERVER)
        self.attempts = 0

    def ensure_connection(self):
        self.attempts += 1


class DatabaseReachableCheckTests(TestCase):
    def setUp(self):
        checks._probe_results.clear()

    def tearDown(self):
        checks._probe_results.clear()

    def test_silent_when_the_database_answers(self):
        self.assertEqual(check_database_reachable(None), [])

    def test_silent_when_the_database_answers_via_the_probe(self):
        connection = _LiveConnection()
        with patch("django.db.connection", connection):
            self.assertEqual(check_database_reachable(None), [])
        self.assertEqual(connection.attempts, 1)

    def test_reports_the_server_it_could_not_reach(self):
        connection = _DeadConnection()
        with patch("django.db.connection", connection), patch.object(
            checks, "_command_name", return_value="runserver"
        ):
            issues = check_database_reachable(None)

        self.assertEqual(len(issues), 1)
        message = issues[0].msg
        self.assertIn("localhost", message)
        self.assertIn("5432", message)
        self.assertIn("zaminex", message)
        self.assertIn("Connection refused", message)
        self.assertEqual(issues[0].id, "database.E001")

    def test_hint_tells_them_how_to_check_the_server(self):
        with patch("django.db.connection", _DeadConnection()), patch.object(
            checks, "_command_name", return_value="runserver"
        ):
            hint = check_database_reachable(None)[0].hint

        self.assertIn("services.msc", hint)
        self.assertIn("systemctl", hint)
        self.assertIn("psql", hint)
        self.assertIn("netstat", hint)
        self.assertIn("DATABASE_CONNECT_TIMEOUT", hint)

    def test_is_an_error_for_runserver(self):
        with patch("django.db.connection", _DeadConnection()), patch.object(
            checks, "_command_name", return_value="runserver"
        ):
            self.assertIsInstance(check_database_reachable(None)[0], Error)

    def test_is_a_warning_for_everything_else(self):
        for command in ("migrate", "makemigrations", "shell", "collectstatic", ""):
            with self.subTest(command=command), patch(
                "django.db.connection", _DeadConnection()
            ), patch.object(checks, "_command_name", return_value=command):
                issue = check_database_reachable(None)[0]
                self.assertIsInstance(issue, CheckWarning)
                self.assertEqual(issue.id, "database.W001")

    def test_command_is_read_from_argv(self):
        with patch("django.db.connection", _DeadConnection()), patch.object(
            sys, "argv", ["manage.py", "runserver", "0.0.0.0:8000"]
        ):
            self.assertIsInstance(check_database_reachable(None)[0], Error)
        checks._probe_results.clear()
        with patch("django.db.connection", _DeadConnection()), patch.object(
            sys, "argv", ["manage.py", "migrate"]
        ):
            self.assertIsInstance(check_database_reachable(None)[0], CheckWarning)

    def test_one_dead_server_is_probed_once_by_all_three_checks(self):
        connection = _DeadConnection()
        with patch("django.db.connection", connection), patch.object(
            checks, "_command_name", return_value="runserver"
        ):
            reported = check_database_reachable(None)
            trgm = check_pg_trgm(None)
            pending = check_pending_migrations(None)

        self.assertEqual(connection.attempts, 1)
        self.assertEqual(len(reported), 1)
        self.assertEqual(trgm, [])
        self.assertEqual(pending, [])

    def test_reports_the_database_url_when_one_is_set(self):
        with patch("django.db.connection", _DeadConnection()), patch.object(
            checks, "_command_name", return_value="runserver"
        ), patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgres://zaminex:zaminex@db.example:5432/zaminex"},
        ):
            hint = check_database_reachable(None)[0].hint

        self.assertIn("DATABASE_URL", hint)

    def test_survives_a_connection_object_with_no_settings(self):
        class _Opaque:
            def __getattr__(self, name):
                raise RuntimeError("no such attribute")

        with patch("django.db.connection", _Opaque()), patch.object(
            checks, "_command_name", return_value="runserver"
        ):
            issues = check_database_reachable(None)

        self.assertEqual(len(issues), 1)
        self.assertIn("Cannot reach the PostgreSQL server", issues[0].msg)


class ConnectTimeoutSettingTests(TestCase):
    def test_the_default_connection_carries_a_connect_timeout(self):
        from django.conf import settings as django_settings

        options = django_settings.DATABASES["default"].get("OPTIONS", {})
        self.assertIn("connect_timeout", options)
        self.assertGreater(int(options["connect_timeout"]), 0)

    def test_the_setting_exposes_the_bound(self):
        from django.conf import settings as django_settings

        self.assertEqual(
            django_settings.DATABASE_CONNECT_TIMEOUT,
            int(
                django_settings.DATABASES["default"]["OPTIONS"]["connect_timeout"]
            ),
        )
