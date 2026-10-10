import logging
import time

from django.test import TestCase, override_settings

from apps.common import cache_utils
from apps.common.throttles import (
    PasswordResetRateThrottle,
    ResilientAnonRateThrottle,
    ResilientScopedRateThrottle,
    ResilientUserRateThrottle,
    _clear_local_history,
)

REDIS_CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache"}}
LOCMEM_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}


class _HealthyCache:
    def __init__(self):
        self.store = {}
        self.sets = 0

    def get(self, key, default=None, version=None):
        return self.store.get(key, default)

    def set(self, key, value, timeout=None, version=None):
        self.store[key] = value
        self.sets += 1
        return True


class _OutageCache:
    def __init__(self):
        self.sets = 0

    def get(self, key, default=None, version=None):
        return default

    def set(self, key, value, timeout=None, version=None):
        self.sets += 1
        return None


class _Request:
    def __init__(self, ident="203.0.113.7"):
        self.META = {"REMOTE_ADDR": ident}
        self.user = None
        self.auth = None


class _AuthenticatedRequest(_Request):
    def __init__(self, ident="203.0.113.7", pk=42):
        super().__init__(ident)
        self.user = type("User", (), {"pk": pk, "is_authenticated": True})()


class _View:
    throttle_scope = "password_reset"


class _AvailabilityTrackingTestsMixin:
    def setUp(self):
        cache_utils.reset_backend_availability()
        _clear_local_history()
        logging.getLogger("apps.common.cache_utils").setLevel(logging.CRITICAL)

    def tearDown(self):
        cache_utils.reset_backend_availability()
        _clear_local_history()
        logging.getLogger("apps.common.cache_utils").setLevel(logging.NOTSET)


class BackendAvailabilityTests(_AvailabilityTrackingTestsMixin, TestCase):
    def test_django_redis_reports_delivery(self):
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            self.assertTrue(cache_utils.backend_reports_delivery())

    def test_locmem_does_not_report_delivery(self):
        with override_settings(CACHES=LOCMEM_CACHES):
            cache_utils.reset_backend_availability()
            self.assertFalse(cache_utils.backend_reports_delivery())
            cache_utils.note_cache_delivered(None)
            self.assertTrue(cache_utils.cache_backend_available())

    def test_swallowed_write_marks_the_backend_down(self):
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            cache_utils.note_cache_delivered(True)
            self.assertTrue(cache_utils.cache_backend_available())
            cache_utils.note_cache_delivered(None)
            self.assertFalse(cache_utils.cache_backend_available())

    def test_backend_is_reprobed_after_the_cooldown(self):
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            original = cache_utils.BACKEND_REPROBE_SECONDS
            cache_utils.BACKEND_REPROBE_SECONDS = 0.05
            try:
                cache_utils.note_cache_delivered(None)
                self.assertFalse(cache_utils.cache_backend_available())
                time.sleep(0.08)
                self.assertTrue(cache_utils.cache_backend_available())
            finally:
                cache_utils.BACKEND_REPROBE_SECONDS = original

    def test_a_recovered_backend_is_used_again(self):
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            cache_utils.note_cache_delivered(None)
            cache_utils.note_cache_delivered(True)
            self.assertTrue(cache_utils.cache_backend_available())


class OutageLoggingTests(_AvailabilityTrackingTestsMixin, TestCase):
    DEAD_CACHE = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:63999/0",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": True,
                "SOCKET_CONNECT_TIMEOUT": 0.2,
                "SOCKET_TIMEOUT": 0.2,
            },
        }
    }

    def test_django_redis_logging_is_enabled(self):
        from django.conf import settings

        self.assertTrue(settings.DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS)

    def test_the_underlying_error_is_logged_with_its_cause(self):
        from django_redis.cache import RedisCache

        backend = RedisCache(
            self.DEAD_CACHE["default"]["LOCATION"], self.DEAD_CACHE["default"]
        )
        self.assertTrue(backend._log_ignored_exceptions)
        with self.assertLogs("django_redis.cache", level="ERROR") as cm:
            self.assertIsNone(backend.get("probe:missing"))
        self.assertIn("Exception ignored", cm.output[0])
        self.assertIn("refused", cm.output[0].lower())

    def test_an_outage_logs_one_warning_not_one_per_request(self):
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            with self.assertLogs("apps.common.cache_utils", level="WARNING") as cm:
                for _ in range(20):
                    cache_utils.note_cache_delivered(None)
            self.assertEqual(len(cm.output), 1)
            self.assertIn("not delivering writes", cm.output[0])

    def test_a_still_down_reprobe_does_not_log_again(self):
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            cache_utils.note_cache_delivered(None)
            with self.assertNoLogs("apps.common.cache_utils", level="WARNING"):
                for _ in range(5):
                    cache_utils.note_cache_delivered(None)

    def test_recovery_logs_one_info_line(self):
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            cache_utils.note_cache_delivered(None)
            with self.assertLogs("apps.common.cache_utils", level="INFO") as cm:
                cache_utils.note_cache_delivered(True)
            self.assertEqual(len(cm.output), 1)
            self.assertIn("delivering writes again", cm.output[0])

    def test_a_healthy_backend_logs_nothing(self):
        with override_settings(CACHES=REDIS_CACHES):
            cache_utils.reset_backend_availability()
            with self.assertNoLogs("apps.common.cache_utils", level="INFO"):
                for _ in range(5):
                    cache_utils.note_cache_delivered(True)


@override_settings(CACHES=REDIS_CACHES)
class ResilientThrottleTests(_AvailabilityTrackingTestsMixin, TestCase):
    def _run(self, throttle, cache, requests, view=_View()):
        throttle.cache = cache
        return [throttle.allow_request(r, view) for r in requests]

    def test_stock_drf_throttle_is_defeated_by_an_outage(self):
        from rest_framework.throttling import ScopedRateThrottle

        results = self._run(
            ScopedRateThrottle(), _OutageCache(), [_Request() for _ in range(8)]
        )
        self.assertEqual(results.count(False), 0)

    def test_scoped_throttle_still_limits_during_an_outage(self):
        results = self._run(
            ResilientScopedRateThrottle(),
            _OutageCache(),
            [_Request() for _ in range(8)],
        )
        self.assertEqual(results, [True] * 5 + [False] * 3)

    def test_password_reset_throttle_still_limits_during_an_outage(self):
        results = self._run(
            PasswordResetRateThrottle(),
            _OutageCache(),
            [_Request() for _ in range(8)],
        )
        self.assertEqual(results, [True] * 5 + [False] * 3)

    def test_anon_throttle_still_limits_during_an_outage(self):
        throttle = ResilientAnonRateThrottle()
        results = self._run(
            throttle, _OutageCache(), [_Request() for _ in range(65)]
        )
        self.assertEqual(results.count(False), 5)

    def test_user_throttle_still_limits_during_an_outage(self):
        throttle = ResilientUserRateThrottle()
        view = type("V", (), {"throttle_scope": None})()
        results = self._run(
            throttle,
            _OutageCache(),
            [_AuthenticatedRequest() for _ in range(305)],
            view=view,
        )
        self.assertEqual(results.count(False), 5)

    def test_per_client_isolation_is_preserved(self):
        cache = _OutageCache()
        throttle = ResilientScopedRateThrottle()
        throttle.cache = cache
        a = _Request(ident="203.0.113.1")
        b = _Request(ident="203.0.113.2")
        for _ in range(5):
            self.assertTrue(throttle.allow_request(a, _View()))
        self.assertFalse(throttle.allow_request(a, _View()))
        self.assertTrue(throttle.allow_request(b, _View()))

    def test_doomed_round_trips_are_skipped_while_down(self):
        cache = _OutageCache()
        throttle = ResilientScopedRateThrottle()
        throttle.cache = cache
        throttle.allow_request(_Request(), _View())
        sets_after_first = cache.sets
        for _ in range(10):
            throttle.allow_request(_Request(), _View())
        self.assertEqual(cache.sets, sets_after_first)

    def test_healthy_backend_uses_the_shared_cache(self):
        cache = _HealthyCache()
        throttle = ResilientScopedRateThrottle()
        results = self._run(throttle, cache, [_Request() for _ in range(8)])
        self.assertEqual(results, [True] * 5 + [False] * 3)
        self.assertTrue(cache.store, "history must live in the shared cache")
        self.assertEqual(cache.sets, 5)

    def test_history_seeded_from_the_failed_write_counts_the_next_request(self):
        cache = _OutageCache()
        throttle = ResilientScopedRateThrottle()
        throttle.cache = cache
        results = [throttle.allow_request(_Request(), _View()) for _ in range(8)]
        self.assertEqual(results.count(True), 5)


class ThrottleRateCoverageTests(TestCase):
    DEFAULT_CLASS_SCOPES = {"anon", "user"}

    def _reachable_api_views(self):
        from django.urls import get_resolver
        from rest_framework.views import APIView

        found = []

        def walk(resolver):
            for pattern in resolver.url_patterns:
                if hasattr(pattern, "url_patterns"):
                    walk(pattern)
                    continue
                callback = pattern.callback
                cls = getattr(callback, "view_class", None) or getattr(callback, "cls", None)
                if cls is not None and issubclass(cls, APIView):
                    found.append(cls)

        walk(get_resolver())
        return found

    def _scopes_in_force(self):
        from rest_framework.throttling import ScopedRateThrottle

        used = set(self.DEFAULT_CLASS_SCOPES)
        for view in self._reachable_api_views():
            classes = getattr(view, "throttle_classes", ()) or ()
            for cls in classes:
                scope = getattr(cls, "scope", None)
                if scope:
                    used.add(scope)

            if any(issubclass(c, ScopedRateThrottle) for c in classes):
                view_scope = getattr(view, "throttle_scope", None)
                if view_scope:
                    used.add(view_scope)
        return used

    def test_the_urlconf_walk_finds_views(self):
        self.assertGreater(len(self._reachable_api_views()), 50)

    def test_the_walk_sees_the_scoped_views(self):
        self.assertIn("ai", self._scopes_in_force())
        self.assertIn("geocode", self._scopes_in_force())

    def test_no_configured_rate_is_dead(self):
        from django.conf import settings

        configured = set(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
        self.assertEqual(
            configured - self._scopes_in_force(),
            set(),
            "rates declared with no view behind them protect nothing",
        )

    def test_no_view_uses_a_scope_without_a_rate(self):
        from django.conf import settings

        configured = set(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
        declared = self._scopes_in_force() - self.DEFAULT_CLASS_SCOPES
        self.assertEqual(
            declared - configured,
            set(),
            "views whose throttle_scope has no matching rate",
        )

    def test_the_expected_scopes_are_the_ones_in_force(self):
        self.assertEqual(
            self._scopes_in_force(),
            {"anon", "user", "password_reset", "ai", "geocode", "sms_request", "sms_verify"},
        )
