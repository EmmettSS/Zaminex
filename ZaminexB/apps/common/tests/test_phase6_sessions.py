from unittest import mock

from django.contrib.sessions.models import Session
from django.core.cache import cache as django_cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import LoginAttempt, User, UserRole
from apps.accounts.tests import extract_login_errors
from apps.common.testing import CacheClearingMixin


class _FailOpenDeadCache:
    def get(self, key, default=None, version=None):
        return default

    def set(self, key, value, timeout=None, version=None):
        return True

    def add(self, key, value, timeout=None, version=None):
        return False

    def delete(self, key, version=None):
        return None

    def has_key(self, key, version=None):
        return False

    def __contains__(self, key):
        return False

    def clear(self, timeout=0):
        return None

    def expire(self, key, timeout=None, version=None):
        return None


def _patch_session_cache(cache):
    return mock.patch(
        "django.contrib.sessions.backends.cached_db.caches",
        mock.MagicMock(**{"__getitem__.return_value": cache}),
    )


def _session_queries(captured):
    return [q for q in captured if "django_session" in q["sql"]]


class Phase6Base(CacheClearingMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="p6-admin", password="p6-pass-123", role=UserRole.ADMIN
        )
        self.client = Client(SERVER_NAME="localhost")

    def _login(self, password="p6-pass-123", username="p6-admin"):
        return self.client.post(
            "/accounts/login/", {"username": username, "password": password}
        )


class SessionSurvivesFlushTests(Phase6Base):
    def test_session_is_persisted_in_the_table(self):
        res = self._login()
        self.assertEqual(res.status_code, 302)
        key = self.client.session.session_key
        self.assertTrue(key)
        self.assertTrue(Session.objects.filter(session_key=key).exists())

    def test_session_survives_a_cache_flush(self):
        res = self._login()
        self.assertEqual(res.status_code, 302)
        key = self.client.session.session_key

        django_cache.clear()
        self.assertFalse(django_cache.get(f"django.contrib.sessions.cached_db{key}"))

        res = self.client.get("/tickets/api/unread-count/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            django_cache.get(f"django.contrib.sessions.cached_db{key}") is not None
        )


class WarmReadSkipsTheSessionTableTests(Phase6Base):
    def test_warm_request_does_one_fewer_session_table_query_than_cold(self):
        self._login()
        django_cache.clear()

        with CaptureQueriesContext(connection) as cold:
            res1 = self.client.get("/tickets/api/unread-count/")
        with CaptureQueriesContext(connection) as warm:
            res2 = self.client.get("/tickets/api/unread-count/")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)

        cold_session = _session_queries(cold.captured_queries)
        warm_session = _session_queries(warm.captured_queries)

        self.assertGreaterEqual(len(cold_session), 1)
        self.assertEqual(len(cold_session) - len(warm_session), 1)


class FailOpenTests(Phase6Base):
    def test_login_requests_and_logout_work_with_a_dead_cache(self):
        dead = _FailOpenDeadCache()
        with _patch_session_cache(dead):
            res = self._login()
            self.assertEqual(res.status_code, 302)
            key = self.client.session.session_key
            self.assertTrue(
                Session.objects.filter(session_key=key).exists()
            )

            res = self.client.get("/tickets/api/unread-count/")
            self.assertEqual(res.status_code, 200)

            res = self.client.post("/accounts/logout/")
            self.assertEqual(res.status_code, 302)

            res = self.client.get("/tickets/api/unread-count/")
            self.assertEqual(res.status_code, 403)

    def test_logout_clears_the_session_from_table_and_cache(self):
        self._login()
        key = self.client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=key).exists())

        res = self.client.post("/accounts/logout/")
        self.assertEqual(res.status_code, 302)

        self.assertFalse(Session.objects.filter(session_key=key).exists())
        self.assertIsNone(
            django_cache.get(f"django.contrib.sessions.cached_db{key}")
        )
        res = self.client.get("/tickets/api/unread-count/")
        self.assertEqual(res.status_code, 403)


class LockoutStillCorrectTests(Phase6Base):
    def test_lockout_blocks_even_the_correct_password(self):
        for _ in range(5):
            res = self._login(password="wrong-pass-1")
            self.assertEqual(res.status_code, 200)
        self.assertTrue(
            LoginAttempt.objects.get(username="p6-admin").locked_until is not None
        )

        res = self._login()
        self.assertEqual(res.status_code, 200)
        errors = extract_login_errors(res.content.decode("utf-8"))
        self.assertTrue(
            any("مسدود" in msg for msg in errors.get("__all__", []))
        )
