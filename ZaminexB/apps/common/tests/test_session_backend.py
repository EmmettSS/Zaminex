import logging
from unittest import mock

from django.contrib.sessions.backends.cached_db import SessionStore as StockSessionStore
from django.test import Client, TestCase, override_settings

from apps.common import cache_utils
from apps.common.session_backend import SessionStore, _SessionCacheGuard

REDIS_CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache"}}


class _CountingCache:
    def __init__(self, healthy=True):
        self.healthy = healthy
        self.store = {}
        self.ops = 0
        self.some_flag = "delegated"

    def get(self, key, default=None, version=None):
        self.ops += 1
        return self.store.get(key, default) if self.healthy else default

    def set(self, key, value, timeout=None, version=None):
        self.ops += 1
        if not self.healthy:
            return None
        self.store[key] = value
        return True

    def delete(self, key, version=None):
        self.ops += 1
        self.store.pop(key, None)
        return True

    def __contains__(self, key):
        self.ops += 1
        return key in self.store


class SessionEngineWiringTests(TestCase):
    def test_settings_name_the_module_not_the_class(self):
        from importlib import import_module

        from django.conf import settings

        module = import_module(settings.SESSION_ENGINE)
        self.assertIs(module.SessionStore, SessionStore)

    def test_the_store_still_is_a_cached_db_store(self):
        self.assertTrue(issubclass(SessionStore, StockSessionStore))

    def test_the_session_cache_is_guarded(self):
        self.assertIsInstance(SessionStore()._cache, _SessionCacheGuard)

    def test_the_guard_is_never_nested(self):
        store = SessionStore()
        SessionStore.__init__(store)
        self.assertIsInstance(store._cache, _SessionCacheGuard)
        self.assertNotIsInstance(store._cache._wrapped, _SessionCacheGuard)


class SessionCacheGuardTests(TestCase):
    def setUp(self):
        cache_utils.reset_backend_availability()
        logging.getLogger("apps.common.cache_utils").setLevel(logging.CRITICAL)

    def tearDown(self):
        cache_utils.reset_backend_availability()
        logging.getLogger("apps.common.cache_utils").setLevel(logging.NOTSET)

    def test_a_healthy_backend_is_delegated_to(self):
        fake = _CountingCache(healthy=True)
        guard = _SessionCacheGuard(fake)
        guard.set("k", {"a": 1}, 60)
        self.assertEqual(guard.get("k"), {"a": 1})
        self.assertIn("k", guard)
        self.assertEqual(fake.ops, 3)

    def test_unknown_attributes_are_delegated(self):
        guard = _SessionCacheGuard(_CountingCache())
        self.assertEqual(guard.some_flag, "delegated")

    def test_a_marked_down_backend_is_not_touched(self):
        fake = _CountingCache(healthy=False)
        guard = _SessionCacheGuard(fake)
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            guard.set("k", {"a": 1}, 60)
            ops = fake.ops
            self.assertIsNone(guard.get("k"))
            self.assertIsNone(guard.set("k", {"a": 1}, 60))
            self.assertIsNone(guard.delete("k"))
            self.assertNotIn("k", guard)
        self.assertEqual(fake.ops, ops, "no operation may reach a down backend")

    def test_a_miss_returns_the_supplied_default(self):
        guard = _SessionCacheGuard(_CountingCache(healthy=True))
        sentinel = object()
        self.assertIs(guard.get("absent", sentinel), sentinel)


class SessionSurvivesAnOutageTests(TestCase):
    def setUp(self):
        from apps.accounts.models import User

        cache_utils.reset_backend_availability()
        logging.getLogger("apps.common.cache_utils").setLevel(logging.CRITICAL)
        self.user = User.objects.create_user(
            username="session-outage", password="pw12345", role="AGENT"
        )

    def tearDown(self):
        cache_utils.reset_backend_availability()
        logging.getLogger("apps.common.cache_utils").setLevel(logging.NOTSET)

    def test_a_logged_in_user_stays_logged_in(self):
        client = Client(SERVER_NAME="localhost")
        client.force_login(self.user)
        self.assertEqual(client.get("/basics/api/catalog/").status_code, 200)

        with mock.patch.object(
            cache_utils, "cache_backend_available", return_value=False
        ):
            res = client.get("/basics/api/catalog/")
        self.assertEqual(res.status_code, 200, "the session must survive the outage")

    def test_the_session_still_round_trips_through_the_cache(self):
        client = Client(SERVER_NAME="localhost")
        client.force_login(self.user)
        session_key = client.session.session_key

        store = SessionStore(session_key)
        self.assertTrue(store.load(), "the session must be readable from the cache")
        self.assertEqual(store["_auth_user_id"], str(self.user.pk))

    def test_a_cold_session_is_loaded_from_the_database_during_an_outage(self):
        from django.core.cache import cache

        client = Client(SERVER_NAME="localhost")
        client.force_login(self.user)
        session_key = client.session.session_key
        cache.delete(SessionStore(session_key).cache_key)
        self.assertFalse(cache.get(SessionStore(session_key).cache_key))

        with mock.patch.object(
            cache_utils, "cache_backend_available", return_value=False
        ):
            data = SessionStore(session_key).load()
        self.assertEqual(data.get("_auth_user_id"), str(self.user.pk))

    def test_a_session_saved_during_an_outage_reaches_the_database(self):
        from django.contrib.sessions.models import Session

        client = Client(SERVER_NAME="localhost")
        client.force_login(self.user)
        session_key = client.session.session_key

        with mock.patch.object(
            cache_utils, "cache_backend_available", return_value=False
        ):
            store = SessionStore(session_key)
            store["written_during_outage"] = "yes"
            store.save()

        row = Session.objects.get(session_key=session_key)
        self.assertEqual(
            SessionStore().decode(row.session_data).get("written_during_outage"), "yes"
        )
