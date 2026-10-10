import json
import urllib.error
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.common.geocode import (
    GeocodeUnavailable,
    clean_viewbox,
    geocode,
    normalize_place_key,
)
from django.contrib.auth import get_user_model

User = get_user_model()

URL = "/common/api/geocode/"

PARITY_CASES = [
    ("خرم‌آباد", "خرماباد"),
    ("خرم اباد", "خرماباد"),
    ("بندر  عباس", "بندرعباس"),
    ("آبادان", "ابادان"),
    ("قائم‌شهر", "قائمشهر"),
    ("قائم شهر", "قائمشهر"),
    ("مشهد", "مشهد"),
    ("", ""),
    (None, ""),
    ("   ", ""),
]


class _FakeResponse:
    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _upstream(rows):
    return mock.patch(
        "apps.common.geocode.urllib.request.urlopen",
        return_value=_FakeResponse(json.dumps(rows)),
    )


def _raise(exc):
    return mock.patch("apps.common.geocode.urllib.request.urlopen", side_effect=exc)


@override_settings(GEOCODE_PACING_SECONDS=0)
class GeocodeTestBase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.create_user(
            username=f"geo-{self._testMethodName}", password="pw-secret-1", role=UserRole.AGENT
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)



class NormalizePlaceKeyTests(TestCase):
    def test_parity_with_the_typescript_implementation(self):
        for raw, expected in PARITY_CASES:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_place_key(raw), expected)

    def test_zwnj_and_a_plain_space_are_the_same_word(self):
        self.assertEqual(normalize_place_key("خرم‌آباد"), normalize_place_key("خرم اباد"))

    def test_arabic_letters_fold_to_their_persian_forms(self):
        self.assertEqual(normalize_place_key("مشهد"), normalize_place_key("مشهد"))
        self.assertEqual(normalize_place_key("يزد"), normalize_place_key("یزد"))
        self.assertEqual(normalize_place_key("كرمان"), normalize_place_key("کرمان"))
        self.assertEqual(normalize_place_key("فاطمه"), normalize_place_key("فاطمه"))
        self.assertEqual(normalize_place_key("موسي"), normalize_place_key("موسی"))

    def test_alef_variants_fold_to_a_plain_alef(self):
        self.assertEqual(normalize_place_key("آبادان"), normalize_place_key("ابادان"))
        self.assertEqual(normalize_place_key("أحمد"), normalize_place_key("احمد"))

    def test_arabic_diacritics_and_tatweel_are_dropped(self):
        self.assertEqual(normalize_place_key("تَهــران"), normalize_place_key("تهران"))

    def test_letter_order_is_never_changed(self):
        self.assertNotEqual(normalize_place_key("تهران"), normalize_place_key("تهرانر"))
        self.assertNotEqual(normalize_place_key("کرج"), normalize_place_key("گرگ"))

    def test_accepts_non_strings(self):
        self.assertEqual(normalize_place_key(12), "12")


class CleanViewboxTests(TestCase):
    def test_four_numbers_are_formatted_to_six_decimals(self):
        self.assertEqual(clean_viewbox("52.1, 36.9,54.4,35.9"), "52.100000,36.900000,54.400000,35.900000")

    def test_wrong_arity_is_rejected(self):
        self.assertIsNone(clean_viewbox("52.1,36.9,54.4"))
        self.assertIsNone(clean_viewbox("52.1,36.9,54.4,35.9,1"))

    def test_non_numeric_is_rejected(self):
        self.assertIsNone(clean_viewbox("52.1,36.9,54.4,abc"))
        self.assertIsNone(clean_viewbox("52.1,36.9,54.4,35.9&countrycodes=us"))

    def test_non_finite_is_rejected(self):
        self.assertIsNone(clean_viewbox("52.1,36.9,inf,35.9"))
        self.assertIsNone(clean_viewbox("52.1,36.9,nan,35.9"))

    def test_empty_is_none_not_invalid(self):
        self.assertIsNone(clean_viewbox(None))
        self.assertIsNone(clean_viewbox(""))



class GeocodeFunctionTests(GeocodeTestBase):
    def test_parses_lat_lon_as_floats_and_keeps_the_address(self):
        with _upstream(
            [
                {
                    "lat": "36.5633",
                    "lon": "53.0601",
                    "display_name": "ساری، مازندران",
                    "address": {"city": "ساری", "state": "مازندران"},
                }
            ]
        ):
            results = geocode("ساری, مازندران")

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0]["lat"], float)
        self.assertIsInstance(results[0]["lon"], float)
        self.assertEqual(results[0]["lat"], 36.5633)
        self.assertEqual(results[0]["address"]["state"], "مازندران")
        self.assertEqual(results[0]["displayName"], "ساری، مازندران")

    def test_asks_for_persian_labels_and_restricts_to_iran(self):
        with _upstream([]) as patched:
            geocode("ساری")
        sent = patched.call_args[0][0]
        query = sent.full_url
        self.assertIn("accept-language=fa", query)
        self.assertIn("countrycodes=ir", query)
        self.assertEqual(sent.get_header("Accept-language"), "fa")
        self.assertTrue(sent.get_header("User-agent"))

    def test_viewbox_is_forwarded_and_bounded_only_when_asked(self):
        with _upstream([]) as patched:
            geocode("ساری", "52.1,36.9,54.4,35.9", bounded=True)
        self.assertIn("bounded=1", patched.call_args[0][0].full_url)
        self.assertIn("viewbox=52.1%2C36.9%2C54.4%2C35.9", patched.call_args[0][0].full_url)

        with _upstream([]) as patched:
            geocode("ساری", "52.1,36.9,54.4,35.9", bounded=False)
        self.assertNotIn("bounded=1", patched.call_args[0][0].full_url)

    def test_second_call_is_served_from_cache(self):
        with _upstream([{"lat": "36.5", "lon": "53.0"}]) as patched:
            first = geocode("ساری")
            second = geocode("ساری")
        self.assertEqual(first, second)
        self.assertEqual(patched.call_count, 1)

    def test_spelling_variants_share_one_cache_entry(self):
        with _upstream([{"lat": "33.4878", "lon": "48.3558"}]) as patched:
            geocode("خرم‌آباد")
            geocode("خرم اباد")
            geocode("خرم اباد ")
        self.assertEqual(patched.call_count, 1)

    @override_settings(GEOCODE_CACHE_TTL=1234, GEOCODE_NEGATIVE_CACHE_TTL=56)
    def test_a_miss_is_cached_for_far_less_than_a_hit(self):
        with mock.patch("apps.common.geocode.cache_utils.cache_set") as cache_set:
            with _upstream([{"lat": "1", "lon": "2"}]):
                geocode("ساری")
            with _upstream([]):
                geocode("تهران-ناموجود")

        self.assertEqual(cache_set.call_count, 2)
        ttls = sorted(call.args[2] for call in cache_set.call_args_list)
        self.assertEqual(ttls, [56, 1234])

    def test_upstream_failure_raises_geocode_unavailable(self):
        for exc in (
            urllib.error.URLError("no route"),
            TimeoutError("too slow"),
            OSError("reset"),
        ):
            with self.subTest(exc=type(exc).__name__):
                with _raise(exc):
                    with self.assertRaises(GeocodeUnavailable):
                        geocode(f"ساری-{type(exc).__name__}")

    def test_a_non_json_body_is_unavailable_not_a_miss(self):
        with mock.patch(
            "apps.common.geocode.urllib.request.urlopen",
            return_value=_FakeResponse("<html>429 Too Many Requests</html>"),
        ):
            with self.assertRaises(GeocodeUnavailable):
                geocode("ساری-html")

    def test_an_unexpected_shape_is_unavailable(self):
        with _upstream({"error": "rate limited"}):
            with self.assertRaises(GeocodeUnavailable):
                geocode("ساری-shape")

    def test_rows_without_coordinates_are_dropped(self):
        with _upstream(
            [{"lat": None, "lon": "53.0"}, {"lat": "oops", "lon": "53.0"}, {"lat": "36.5", "lon": "53.0"}]
        ):
            results = geocode("ساری-rows")
        self.assertEqual(len(results), 1)

    @override_settings(GEOCODE_PACING_SECONDS=0.2)
    def test_pacing_reserves_a_slot_in_the_shared_cache(self):
        from apps.common import cache_utils
        from apps.common.geocode import _pace

        slot = cache_utils.make_key("geocode", "pace")
        cache_utils.cache_delete(slot)
        _pace()
        self.assertIsNotNone(cache_utils.cache_get(slot))

    @override_settings(GEOCODE_PACING_SECONDS=0)
    def test_pacing_is_disabled_at_zero(self):
        from apps.common import cache_utils
        from apps.common.geocode import _pace

        slot = cache_utils.make_key("geocode", "pace")
        cache_utils.cache_delete(slot)
        _pace()
        self.assertIsNone(cache_utils.cache_get(slot))

    @override_settings(GEOCODE_PACING_SECONDS=0.15)
    def test_a_busy_slot_is_waited_out_then_sent_anyway(self):
        import time as _time

        from apps.common import cache_utils
        from apps.common.geocode import _pace

        slot = cache_utils.make_key("geocode", "pace")
        cache_utils.cache_delete(slot)
        _pace()
        started = _time.monotonic()
        _pace()
        elapsed = _time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.1)
        self.assertLess(elapsed, 3.0)

    @override_settings(GEOCODE_PACING_SECONDS=0.5)
    def test_only_one_of_many_concurrent_callers_takes_the_slot(self):
        import threading
        import time as _time

        from apps.common import cache_utils
        from apps.common.geocode import _pace

        window = 0.5
        slot = cache_utils.make_key("geocode", "pace")
        cache_utils.cache_delete(slot)

        acquired = []
        lock = threading.Lock()
        real_add = cache_utils.cache_add

        def counting_add(key, value, timeout):
            result = real_add(key, value, timeout)
            if result is not False:
                with lock:
                    acquired.append(_time.monotonic())
            return result

        concurrency = 32
        barrier = threading.Barrier(concurrency)

        def worker():
            barrier.wait()
            _pace()

        with mock.patch.object(cache_utils, "cache_add", counting_add):
            started = _time.monotonic()
            threads = [threading.Thread(target=worker) for _ in range(concurrency)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        in_first_window = [t for t in acquired if t - started < window]
        self.assertEqual(
            len(in_first_window),
            1,
            f"{len(in_first_window)} callers escaped the first pacing window",
        )

    @override_settings(GEOCODE_PACING_SECONDS=1.1)
    def test_an_unavailable_cache_makes_pacing_proceed_not_block(self):
        import time as _time

        from apps.common import cache_utils
        from apps.common.geocode import _pace

        with mock.patch.object(cache_utils, "cache_add", return_value=None):
            started = _time.monotonic()
            _pace()
            elapsed = _time.monotonic() - started
        self.assertLess(elapsed, 0.2, f"_pace() blocked for {elapsed:.2f}s")



class GeocodeViewTests(GeocodeTestBase):
    def test_anonymous_caller_is_rejected(self):
        client = APIClient()
        with _upstream([{"lat": "36.5", "lon": "53.0"}]):
            response = client.get(URL, {"q": "ساری"})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_hit_returns_a_bare_array(self):
        with _upstream([{"lat": "36.5633", "lon": "53.0601", "address": {"city": "ساری"}}]):
            response = self.client.get(URL, {"q": "ساری"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIsInstance(body, list)
        self.assertEqual(body[0]["lat"], 36.5633)

    def test_no_match_is_200_with_an_empty_array(self):
        with _upstream([]):
            response = self.client.get(URL, {"q": "جای‌ناموجود"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_unreachable_upstream_is_503_not_404(self):
        with _raise(urllib.error.URLError("no route")):
            response = self.client.get(URL, {"q": "ساری"})
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("در دسترس نیست", response.json()["detail"])

    def test_empty_query_is_400_with_a_persian_message(self):
        response = self.client.get(URL, {"q": "   "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.json()["detail"])

    def test_missing_query_is_400(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(GEOCODE_MAX_QUERY_LENGTH=12)
    def test_overlong_query_is_400(self):
        response = self.client.get(URL, {"q": "س" * 13})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_viewbox_is_400_and_never_forwarded(self):
        with _upstream([]) as patched:
            response = self.client.get(
                URL, {"q": "ساری", "viewbox": "52.1,36.9,54.4,35.9&countrycodes=us"}
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(patched.call_count, 0)

    def test_valid_viewbox_is_normalised_and_forwarded(self):
        with _upstream([]) as patched:
            response = self.client.get(
                URL, {"q": "ساری", "viewbox": " 52.1, 36.9 ,54.4,35.9 ", "bounded": "1"}
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sent = patched.call_args[0][0].full_url
        self.assertIn("viewbox=52.100000%2C36.900000%2C54.400000%2C35.900000", sent)
        self.assertIn("bounded=1", sent)

    def test_bounded_accepts_the_common_truthy_spellings(self):
        for value in ("1", "true", "yes"):
            with self.subTest(value=value):
                with _upstream([]) as patched:
                    self.client.get(URL, {"q": f"ساری-{value}", "viewbox": "1,2,3,4", "bounded": value})
                self.assertIn("bounded=1", patched.call_args[0][0].full_url)

    def test_bounded_ignores_anything_else(self):
        with _upstream([]) as patched:
            self.client.get(URL, {"q": "ساری-x", "viewbox": "1,2,3,4", "bounded": "on"})
        self.assertNotIn("bounded=1", patched.call_args[0][0].full_url)

    def test_the_same_query_is_served_from_cache_across_requests(self):
        with _upstream([{"lat": "36.5", "lon": "53.0"}]) as patched:
            self.client.get(URL, {"q": "ساری"})
            self.client.get(URL, {"q": "ساری"})
        self.assertEqual(patched.call_count, 1)

    def test_throttled_with_its_own_scope(self):
        from rest_framework.throttling import ScopedRateThrottle

        from apps.common.views import GeocodeView

        self.assertTrue(
            all(issubclass(c, ScopedRateThrottle) for c in GeocodeView.throttle_classes),
            GeocodeView.throttle_classes,
        )
        self.assertEqual(GeocodeView.throttle_scope, "geocode")

    def test_the_endpoint_is_registered_under_the_common_api_prefix(self):
        from django.urls import reverse

        self.assertEqual(reverse("geocode"), URL)
