import io
import threading
import time
from unittest import mock

from django.core.management import call_command
from django.test import Client, TestCase, TransactionTestCase

from apps.accounts.models import ConsultantProfile, User
from apps.common import cache_utils
from apps.analytics.ai_service import get_cached_description
from apps.analytics.models import AIInsightCache
from apps.common.models import CompanySettings


class _SharedStore:
    def __init__(self):
        self.store: dict = {}

    def backend(self, name: str):
        store = self.store

        class _Backend:
            def get(self, key, default=None):
                return store.get(key, default)

            def set(self, key, value, timeout=None):
                store[key] = value
                return True

            def add(self, key, value, timeout=None):
                if key in store:
                    return False
                store[key] = value
                return True

            def delete(self, key):
                store.pop(key, None)

            def clear(self):
                store.clear()

        return _Backend()


def _ai_raw(name: str) -> str:
    return (
        '{"positives":["+1","+2","+3"],"negatives":["-1","-2","-3"],'
        '"summary":"خلاصه برای ' + name + '"}'
    )


class Phase3Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="p3-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="p3-agent", password="pw", role="AGENT"
        )
        cls.profile = ConsultantProfile.objects.create(
            user=cls.agent, full_name="احمد", branch="مرکزی"
        )

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        AIInsightCache.objects.all().delete()
        s = CompanySettings.get_solo()
        s.ai_enabled = True
        s.ai_api_base_url = "https://mock.example/v1"
        s.ai_api_key = "k"
        s.ai_model = "m"
        s.save()

    def _data(self, **extra):
        data = {"name": "احمد", "kpis": {"openTasks": 3}}
        data.update(extra)
        return data


class AICacheCrossProcessTests(Phase3Base):
    def test_second_process_serves_the_shared_cache_without_llm_call(self):
        store = _SharedStore()

        with mock.patch.object(cache_utils, "_cache", return_value=store.backend("worker-a")), \
             mock.patch("apps.analytics.ai_service._chat_completion", return_value=_ai_raw("احمد")) as m:
            first = get_cached_description(
                self._data(), entity="consultant", entity_id=self.profile.pk
            )
        self.assertEqual(m.call_count, 1)

        AIInsightCache.objects.all().delete()

        with mock.patch.object(cache_utils, "_cache", return_value=store.backend("worker-b")), \
             mock.patch("apps.analytics.ai_service._chat_completion", return_value=_ai_raw("احمد")) as m2:
            second = get_cached_description(
                self._data(), entity="consultant", entity_id=self.profile.pk
            )
        self.assertEqual(m2.call_count, 0)
        self.assertEqual(first, second)

    def test_cache_key_is_versioned_and_json_encoded(self):
        store = _SharedStore()
        with mock.patch.object(cache_utils, "_cache", return_value=store.backend("w")), \
             mock.patch("apps.analytics.ai_service._chat_completion", return_value=_ai_raw("احمد")):
            get_cached_description(
                self._data(), entity="consultant", entity_id=self.profile.pk
            )
        keys = list(store.store.keys())
        self.assertEqual(len(keys), 1)
        self.assertTrue(keys[0].startswith(f"zaminex:{cache_utils.CACHE_VERSION}:ai:desc:"))
        raw = store.store[keys[0]]
        self.assertIsInstance(raw, str)
        import json

        decoded = json.loads(raw)
        self.assertIn("fingerprint", decoded)
        self.assertIn("summary", decoded["description"])

    def test_changed_data_still_triggers_regeneration(self):
        store = _SharedStore()
        with mock.patch.object(cache_utils, "_cache", return_value=store.backend("w")), \
             mock.patch("apps.analytics.ai_service._chat_completion", return_value=_ai_raw("احمد")) as m:
            get_cached_description(self._data(), entity="consultant", entity_id=self.profile.pk)
            get_cached_description(
                self._data(kpis={"openTasks": 99}), entity="consultant", entity_id=self.profile.pk
            )
        self.assertEqual(m.call_count, 2)


class AIHerdProtectionTests(TransactionTestCase):
    serializable_transactions = False

    def setUp(self):
        call_command("seed_basics", stdout=io.StringIO())
        self.agent = User.objects.create_user(
            username="p3-herd-agent", password="pw", role="AGENT"
        )
        self.profile = ConsultantProfile.objects.create(
            user=self.agent, full_name="احمد", branch="مرکزی"
        )
        s = CompanySettings.get_solo()
        s.ai_enabled = True
        s.ai_api_base_url = "https://mock.example/v1"
        s.ai_api_key = "k"
        s.ai_model = "m"
        s.save()

    def _data(self):
        return {"name": "احمد", "kpis": {"openTasks": 3}}

    def test_concurrent_cold_requests_generate_exactly_once(self):
        calls: list = []
        results: list = []
        errors: list = []
        barrier = threading.Barrier(5)

        def slow_chat_completion(system, user):
            calls.append(time.monotonic())
            time.sleep(0.3)
            return _ai_raw("احمد")

        def worker():
            try:
                barrier.wait()
                results.append(
                    get_cached_description(
                        self._data(), entity="consultant", entity_id=self.profile.pk
                    )
                )
            except Exception as exc:
                errors.append(exc)
            finally:
                from django.db import connection

                connection.close()

        with mock.patch("apps.analytics.ai_service._chat_completion", side_effect=slow_chat_completion):
            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 1, "the herd must pay for exactly one model call")
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(
            AIInsightCache.objects.filter(entity="consultant", entity_id=self.profile.pk).count(),
            1,
        )


class AIFailOpenTests(Phase3Base):
    class _DeadCache:
        def __getattr__(self, _name):
            raise ConnectionError("redis is down")

    def test_dead_cache_serves_from_the_db_without_llm_call(self):
        with mock.patch("apps.analytics.ai_service._chat_completion", return_value=_ai_raw("احمد")) as m:
            first = get_cached_description(
                self._data(), entity="consultant", entity_id=self.profile.pk
            )
        self.assertEqual(m.call_count, 1)

        with mock.patch.object(cache_utils, "_cache", return_value=self._DeadCache()), \
             mock.patch("apps.analytics.ai_service._chat_completion", return_value=_ai_raw("احمد")) as m2:
            second = get_cached_description(
                self._data(), entity="consultant", entity_id=self.profile.pk
            )
        self.assertEqual(m2.call_count, 0)
        self.assertEqual(first, second)


class GlobalThrottleTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_password_reset_limit_is_shared_across_two_connections(self):
        c1 = Client()
        c2 = Client()
        body = {"username": "ghost-user-p3"}

        for i in range(5):
            res = (c1 if i % 2 == 0 else c2).post(
                "/common/api/password-reset-request/", body, format="json"
            )
            self.assertEqual(res.status_code, 200, f"request {i + 1} should pass")

        res = c1.post("/common/api/password-reset-request/", body, format="json")
        self.assertEqual(res.status_code, 429)


class WithLockTests(TestCase):
    def test_lock_is_acquired_and_released(self):
        from django.core.cache import cache

        key = cache_utils.make_key("test", "lock-basic")
        with cache_utils.with_lock(key) as owned:
            self.assertTrue(owned)
            self.assertIsNotNone(cache.get(key))
        self.assertIsNone(cache.get(key))

    def test_second_lock_waits_for_the_first_holder(self):
        key = cache_utils.make_key("test", "lock-wait")
        order: list = []

        def first_holder():
            with cache_utils.with_lock(key, wait=2):
                order.append("first-in")
                time.sleep(0.3)
                order.append("first-out")

        thread = threading.Thread(target=first_holder)
        thread.start()
        time.sleep(0.1)

        t0 = time.monotonic()
        with cache_utils.with_lock(key, wait=2) as owned:
            order.append("second-in")
        waited = time.monotonic() - t0
        thread.join()

        self.assertGreaterEqual(waited, 0.15)
        self.assertEqual(order, ["first-in", "first-out", "second-in"])

    def test_dead_backend_is_fail_open(self):
        class _Dead:
            def __getattr__(self, _name):
                raise ConnectionError("down")

        key = cache_utils.make_key("test", "lock-dead")
        with mock.patch.object(cache_utils, "_cache", return_value=_Dead()):
            with cache_utils.with_lock(key) as owned:
                self.assertFalse(owned)
