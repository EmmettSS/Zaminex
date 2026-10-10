import importlib
import re

from django.db import connection, transaction
from django.test import TestCase

from apps.common import fuzzy_search
from apps.common.fuzzy_search import (
    FUZZY_SEARCH_THRESHOLD,
    _index_expression,
    _set_trgm_gate,
    apply_fuzzy_search,
)
from apps.properties.models import Property

FIELDS = ["title", "internal_code", "address", "neighborhood"]


def _explain(queryset):
    sql, params = queryset.query.sql_with_params()
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
        try:
            cursor.execute("EXPLAIN " + sql, params)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.execute("SET LOCAL enable_seqscan = on")


class GateThresholdTests(TestCase):
    def test_gate_sits_below_the_scoring_threshold(self):
        gate = _set_trgm_gate(FUZZY_SEARCH_THRESHOLD)
        self.assertLess(gate, FUZZY_SEARCH_THRESHOLD)
        self.assertGreater(gate, 0)

    def test_gate_is_applied_to_the_session(self):
        _set_trgm_gate(FUZZY_SEARCH_THRESHOLD)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_setting('pg_trgm.word_similarity_threshold'),"
                "       current_setting('pg_trgm.similarity_threshold')"
            )
            word, plain = cursor.fetchone()
        self.assertLess(float(word), FUZZY_SEARCH_THRESHOLD)
        self.assertLess(float(plain), FUZZY_SEARCH_THRESHOLD)

    def test_gate_never_drops_a_row_the_score_keeps(self):
        agent_title = "آپارتمان لوکس نیاوران"
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="gate-user", password="pw", role="ADMIN"
        )
        Property.objects.bulk_create(
            [
                Property(
                    consultant=user, title=agent_title, property_type="APARTMENT",
                    deal_type="SALE", address="تهران", neighborhood="نیاوران",
                    area=120, internal_code="ZF_7900",
                )
            ]
        )
        gated = apply_fuzzy_search(Property.objects.all(), "اپارتمان لوکس", FIELDS)
        gated_ids = set(gated.values_list("id", flat=True))

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM properties_property WHERE similarity(%s, %s) >= %s",
                [
                    "اپارتمان لوکس",
                    agent_title.replace("\u200c", "").upper(),
                    FUZZY_SEARCH_THRESHOLD,
                ],
            )
            reference_ids = {row[0] for row in cursor.fetchall()}

        self.assertTrue(reference_ids, "reference set must be non-empty to be a test")
        self.assertTrue(reference_ids <= gated_ids)


class GateOperandOrderTests(TestCase):
    def test_single_word_gate_uses_the_less_than_percent_operator(self):
        qs = apply_fuzzy_search(Property.objects.all(), "اپارتمان", FIELDS)
        sql, _ = qs.query.sql_with_params()
        self.assertIn("<%", sql, "the word-similarity gate must use <%")
        self.assertNotIn(" %>", sql, "%> reverses the operands and scores 0")

    def test_multi_word_gate_uses_the_percent_operator(self):
        qs = apply_fuzzy_search(Property.objects.all(), "اپارتمان لوکس", FIELDS)
        sql, _ = qs.query.sql_with_params()
        self.assertRegex(sql, r"%%| % ", "the phrase gate must use %")

    def test_gate_scores_the_query_against_the_field_not_the_reverse(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="order-user", password="pw", role="ADMIN"
        )
        prop = Property.objects.bulk_create(
            [
                Property(
                    consultant=user, title="آپارتمان لوکس نیاوران",
                    property_type="APARTMENT", deal_type="SALE",
                    address="تهران", neighborhood="نیاوران",
                    area=120, internal_code="ZF_7901",
                )
            ]
        )[0]
        ids = set(
            apply_fuzzy_search(
                Property.objects.all(), "اپارتمان", FIELDS
            ).values_list("id", flat=True)
        )
        self.assertIn(prop.id, ids, "typo of a word inside a long title must match")


class IndexExpressionAgreementTests(TestCase):
    def test_migrations_strip_the_same_character_as_the_normalizer(self):
        modules = [
            importlib.import_module(
                "apps.properties.migrations.0016_fuzzy_search_trgm_indexes"
            ),
            importlib.import_module(
                "apps.listings.migrations.0008_fuzzy_search_trgm_indexes"
            ),
        ]
        self.assertEqual(
            fuzzy_search.normalize_persian_text("می\u200cخواهم"), "میخواهم"
        )
        for module in modules:
            self.assertEqual(module.ZWNJ, "\u200c", module.__name__)
            self.assertIn(module.ZWNJ, module._expression("title"))

    def test_searched_columns_are_the_indexed_columns(self):
        listings_indexes = importlib.import_module(
            "apps.listings.migrations.0008_fuzzy_search_trgm_indexes"
        )
        properties_indexes = importlib.import_module(
            "apps.properties.migrations.0016_fuzzy_search_trgm_indexes"
        )

        indexed = {
            column for _, column, _ in properties_indexes._TARGETS
        } | {column for _, column, _ in listings_indexes._TARGETS}
        self.assertLessEqual(
            {"title", "internal_code", "address", "neighborhood"}, indexed
        )
        self.assertLessEqual({"description"}, indexed)

    def test_the_gin_indexes_exist(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes WHERE indexname LIKE '%_trgm_idx'"
            )
            names = {row[0] for row in cursor.fetchall()}
        self.assertIn("properties_property_title_trgm_idx", names)
        self.assertIn("listings_listing_title_trgm_idx", names)


class IndexUsageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        cls.user = get_user_model().objects.create_user(
            username="plan-user", password="pw", role="ADMIN"
        )
        Property.objects.bulk_create(
            [
                Property(
                    consultant=cls.user,
                    title=f"آپارتمان نوساز پونک {i}",
                    property_type="APARTMENT",
                    deal_type="SALE",
                    status=Property.Status.AVAILABLE,
                    area=100,
                    address=f"خیابان {i}",
                    neighborhood="پونک",
                    price=1_000_000_000 + i,
                    internal_code=f"ZP_{i:06d}",
                )
                for i in range(300)
            ]
        )

        with connection.cursor() as cursor:
            cursor.execute("ANALYZE properties_property")

    def test_single_word_search_uses_the_trigram_index(self):
      with transaction.atomic():
        self._test_single_word_search_uses_the_trigram_index()

    def _test_single_word_search_uses_the_trigram_index(self):
        plan = "\n".join(
            _explain(apply_fuzzy_search(Property.objects.all(), "اپارتمان", FIELDS))
        )
        self.assertIn("Bitmap Index Scan", plan)
        self.assertIn("properties_property_title_trgm_idx", plan)

    def test_exact_substring_search_uses_the_trigram_index(self):
      with transaction.atomic():
        self._test_exact_substring_search_uses_the_trigram_index()

    def _test_exact_substring_search_uses_the_trigram_index(self):
        plan = "\n".join(
            _explain(apply_fuzzy_search(Property.objects.all(), "آپارتمان", FIELDS))
        )
        self.assertIn("Bitmap Index Scan", plan)

    def test_multi_word_search_uses_the_trigram_index(self):
      with transaction.atomic():
        self._test_multi_word_search_uses_the_trigram_index()

    def _test_multi_word_search_uses_the_trigram_index(self):
        plan = "\n".join(
            _explain(
                apply_fuzzy_search(Property.objects.all(), "آپارتمان نوساز", FIELDS)
            )
        )
        self.assertIn("Bitmap Index Scan", plan)

    def test_query_is_not_a_plain_sequential_scan(self):
      with transaction.atomic():
        self._test_query_is_not_a_plain_sequential_scan()

    def _test_query_is_not_a_plain_sequential_scan(self):
        plan = "\n".join(
            _explain(apply_fuzzy_search(Property.objects.all(), "اپارتمان", FIELDS))
        )
        self.assertNotIn("Seq Scan on properties_property", plan)


class BehaviourPreservedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        cls.user = get_user_model().objects.create_user(
            username="behaviour-user", password="pw", role="ADMIN"
        )
        
        Property.objects.bulk_create(
            [
                Property(
                    consultant=cls.user, title=title, internal_code=code,
                    property_type="APARTMENT", deal_type="SALE",
                    address="تهران", neighborhood="سعادت آباد", area=100,
                )
                for code, title in (
                    ("ZF_7100", "آپارتمان دو خواب"),
                    ("ZF_7200", "ویلا دوبلکس"),
                    ("ZF_7300", "می\u200cخواهم"),
                )
            ]
        )

    def _codes(self, query):
        rows = apply_fuzzy_search(Property.objects.all(), query, FIELDS)
        return {row.internal_code for row in rows}

    def test_exact_term(self):
        self.assertEqual(self._codes("آپارتمان"), {"ZF_7100"})

    def test_typo_is_still_tolerated(self):
        self.assertEqual(self._codes("اپارتمان"), {"ZF_7100"})

    def test_zwnj_variants_both_match(self):
        self.assertEqual(self._codes("میخواهم"), {"ZF_7300"})
        self.assertEqual(self._codes("می\u200cخواهم"), {"ZF_7300"})

    def test_word_boundary_noise_is_rejected(self):
        self.assertNotIn("ZF_7300", self._codes("خواب"))

    def test_internal_code_search_is_exact_not_fuzzy(self):
        self.assertEqual(self._codes("ZF_72"), {"ZF_7200"})
        self.assertEqual(self._codes("ZF_7100"), {"ZF_7100"})

    def test_internal_code_search_is_case_insensitive(self):
        self.assertEqual(self._codes("zf_7200"), {"ZF_7200"})

    def test_dissimilar_term_matches_nothing(self):
        self.assertEqual(self._codes("کافه"), set())

    def test_relevance_ordering_is_preserved(self):
        rows = list(apply_fuzzy_search(Property.objects.all(), "ویلا", FIELDS))
        self.assertEqual(rows[0].internal_code, "ZF_7200")
