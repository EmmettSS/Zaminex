import difflib
import random

from django.contrib.auth import get_user_model
from django.db.models import Case
from django.test import TestCase
from unittest.mock import patch

from apps.common.fuzzy_search import (
    _score_ordering,
    _token_ratio,
    apply_fuzzy_search,
)
from apps.properties.models import Property

User = get_user_model()

FIELDS = ["title", "internal_code", "address", "neighborhood"]


def _make_property(title, code, agent, **kwargs):
    defaults = dict(
        property_type="APARTMENT",
        deal_type="SALE",
        area=80,
        address="تهران",
        neighborhood="",
    )
    defaults.update(kwargs)
    return Property.objects.create(
        title=title, internal_code=code, consultant=agent, **defaults
    )


def _reference_score(query, value):
    from apps.common.fuzzy_search import normalize_persian_text

    norm_val = normalize_persian_text(value)
    if not norm_val:
        return 0.0
    if query in norm_val:
        return 1.0
    q_trigrams = set(query[i:i + 3] for i in range(max(1, len(query) - 2)))
    v_trigrams = set(norm_val[i:i + 3] for i in range(max(1, len(norm_val) - 2)))
    best = 0.0
    if q_trigrams and v_trigrams:
        best = len(q_trigrams & v_trigrams) / float(len(q_trigrams | v_trigrams))
    for q_tok in query.split():
        for v_tok in norm_val.split():
            ratio = difflib.SequenceMatcher(None, q_tok, v_tok).ratio()
            if ratio >= 0.70:
                best = max(best, ratio)
    return best


class TokenRatioTests(TestCase):
    def test_matches_sequencematcher_on_real_persian_pairs(self):
        pairs = [
            ("مشاهر", "مشاور"),
            ("اپارتمان", "آپارتمان"),
            ("خواب", "میخواهم"),
            ("تهران", "تهرانپارس"),
            ("ویلا", "ویلادوبلکس"),
            ("a", "b"),
            ("", ""),
            ("نی", "نیاوران"),
        ]
        for a, b in pairs:
            expected = difflib.SequenceMatcher(None, a, b).ratio()
            got = _token_ratio(a, b)
            if expected >= 0.70:
                self.assertAlmostEqual(got, expected, places=10, msg=f"{a!r} vs {b!r}")
            elif got != 0.0:
                self.assertAlmostEqual(got, expected, places=10, msg=f"{a!r} vs {b!r}")

    def test_length_prefilter_never_hides_a_pair_that_would_pass(self):
        rng = random.Random(20240607)
        alphabet = "آپارتمانلوکسدوخوابویلا" + "abcdefghij"
        for _ in range(4000):
            a = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 12)))
            b = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 12)))
            truth = difflib.SequenceMatcher(None, a, b).ratio()
            got = _token_ratio(a, b)
            if got == 0.0:
                self.assertLess(
                    truth, 0.70,
                    f"prefilter discarded {a!r}/{b!r} which really scores {truth}",
                )
            else:
                self.assertAlmostEqual(got, truth, places=10)

    def test_result_is_memoised(self):
        _token_ratio.cache_clear()
        _token_ratio("مشاهر", "مشاور")
        _token_ratio("مشاهر", "مشاور")
        info = _token_ratio.cache_info()
        self.assertEqual(info.hits, 1)
        self.assertEqual(info.misses, 1)


class ScoreOrderingTests(TestCase):
    def test_one_branch_per_distinct_score(self):
        scored = [(pk, 1.0) for pk in range(1, 501)]
        scored += [(pk, 0.8) for pk in range(501, 506)]
        expression = _score_ordering(scored)
        self.assertIsInstance(expression, Case)
        self.assertEqual(len(expression.cases), 2)

    def test_branches_follow_descending_score_order(self):
        scored = [(1, 1.0), (2, 0.9), (3, 0.9), (4, 0.5)]
        expression = _score_ordering(scored)
        ranks = [case.result.value for case in expression.cases]
        self.assertEqual(ranks, [0, 1, 2])
        self.assertEqual(expression.cases[0].result.value, 0)

    def test_single_row_still_orders(self):
        expression = _score_ordering([(7, 0.42)])
        self.assertEqual(len(expression.cases), 1)


@patch("apps.common.fuzzy_search._pg_trgm_available", return_value=False)
class FallbackPathTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(
            username="fallback_agent", password="x", role="AGENT"
        )
        _make_property("آپارتمان لوکس نیاوران", "ZF_8101", cls.agent,
                       neighborhood="نیاوران")
        _make_property("ویلا دوبلکس شهرک غرب", "ZF_8102", cls.agent,
                       neighborhood="شهرک غرب")
        _make_property("مرکز مشاور املاک پونک", "ZF_8103", cls.agent,
                       neighborhood="پونک")

    def test_typo_is_still_found_without_pg_trgm(self, _mock):
        results = apply_fuzzy_search(
            Property.objects.all(), "مشاهر", FIELDS
        ).values_list("title", flat=True)
        self.assertIn("مرکز مشاور املاک پونک", list(results))

    def test_matches_the_pre_fix_implementation(self, _mock):
        from apps.common.fuzzy_search import normalize_persian_text

        for query in ("اپارتمان", "مشاهر", "ویلا", "لوکس"):
            _token_ratio.cache_clear()
            normalized = normalize_persian_text(query)
            expected = {
                p.pk
                for p in Property.objects.all()
                if max(
                    [_reference_score(normalized, getattr(p, f) or "")
                     for f in ("title", "address", "neighborhood")] + [0.0]
                ) >= 0.15
            }
            got = set(
                apply_fuzzy_search(Property.objects.all(), query, FIELDS)
                .values_list("pk", flat=True)
            )
            self.assertEqual(got, expected, f"query {query!r}")

    def test_ordering_is_deterministic_across_calls(self, _mock):
        _token_ratio.cache_clear()
        first = list(
            apply_fuzzy_search(Property.objects.all(), "اپارتمان", FIELDS)
            .values_list("pk", flat=True)
        )
        _token_ratio.cache_clear()
        second = list(
            apply_fuzzy_search(Property.objects.all(), "اپارتمان", FIELDS)
            .values_list("pk", flat=True)
        )
        self.assertEqual(first, second)

    def test_exact_substring_short_circuits_the_scan(self, _mock):
        queryset = apply_fuzzy_search(
            Property.objects.all(), "نیاوران", FIELDS
        )
        sql, _ = queryset.query.sql_with_params()
        self.assertNotIn("CASE", sql)
        self.assertEqual(
            list(queryset.values_list("title", flat=True)),
            ["آپارتمان لوکس نیاوران"],
        )

    def test_no_match_returns_empty_not_the_whole_table(self, _mock):
        _token_ratio.cache_clear()
        self.assertEqual(
            list(
                apply_fuzzy_search(
                    Property.objects.all(), "ژژژژژژژ", FIELDS
                ).values_list("pk", flat=True)
            ),
            [],
        )
