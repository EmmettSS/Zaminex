"""Tests for the shared server-side search helper and the search APIs.

The matching engine uses PostgreSQL pg_trgm (TrigramSimilarity) and Persian
normalization pipeline: Persian/Arabic tolerance, ZWNJ handling, multi-word
queries, pagination integrity and role scoping.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.common.fuzzy_search import apply_fuzzy_search, normalize_persian_text
from apps.listings.models import Listing
from apps.properties.models import Property

User = get_user_model()


def _make_property(title, code, agent, **kwargs):
    defaults = dict(
        property_type="APARTMENT",
        deal_type="SALE",
        area=80,
        address="تهران",
        neighborhood="",
    )
    defaults.update(kwargs)
    return Property.objects.create(title=title, internal_code=code, consultant=agent, **defaults)


class NormalizePersianTextTests(TestCase):
    """The normalization pipeline must make Arabic variants equivalent."""

    def test_arabic_letters_unify_to_persian(self):
        # Arabic kaf (U+0643) -> Persian kaf (U+06A9)
        self.assertEqual(normalize_persian_text("\u0643"), "ک")
        # Arabic ye (U+064A) and alef maksura (U+0649) -> Persian ye (U+06CC)
        self.assertEqual(normalize_persian_text("\u064a"), "ی")
        self.assertEqual(normalize_persian_text("\u0649"), "ی")

    def test_digits_unify_to_ascii(self):
        self.assertEqual(normalize_persian_text("۱۲۳"), "123")
        self.assertEqual(normalize_persian_text("٠٩"), "09")

    def test_zwnj_is_removed(self):
        self.assertEqual(normalize_persian_text("می\u200cخواهم"), "میخواهم")

    def test_whitespace_is_collapsed_and_trimmed(self):
        self.assertEqual(normalize_persian_text("  آپارتمان   دو  "), "آپارتمان دو")

    def test_empty_input(self):
        self.assertEqual(normalize_persian_text(""), "")
        self.assertEqual(normalize_persian_text(None), "")


class ApplyFuzzySearchTests(TestCase):
    """Direct unit tests for the shared helper."""

    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(username="fs-agent", password="pw", role="AGENT")
        cls.apartment = _make_property("آپارتمان دو خواب", "A-100", cls.agent)
        cls.villa = _make_property("ویلا ساحلی", "V-200", cls.agent, property_type="VILLA")
        cls.office = _make_property("دفتر کار مرکزی", "O-300", cls.agent, property_type="OFFICE", deal_type="RENT")
        cls.consultancy = _make_property("مرکز مشاور املاک", "M-400", cls.agent)
        cls.cafe = _make_property("کافه", "K-500", cls.agent)
        cls.zwnj = _make_property("می\u200cخواهم", "Z-600", cls.agent)

    FIELDS = ["title", "internal_code", "address"]

    def _codes(self, query):
        qs = apply_fuzzy_search(Property.objects.all(), query, self.FIELDS)
        return set(qs.values_list("internal_code", flat=True))

    def test_exact_persian_term_is_matched(self):
        self.assertEqual(self._codes("آپارتمان"), {"A-100"})

    def test_typo_is_tolerated(self):
        # Missing hamza on the alef: اپارتمان vs آپارتمان
        self.assertEqual(self._codes("اپارتمان"), {"A-100"})

    def test_transposed_characters_are_tolerated(self):
        # مشاهر is مشاور with two characters swapped.
        self.assertEqual(self._codes("مشاهر"), {"M-400"})

    def test_arabic_variant_letters_are_matched(self):
        # Type the Arabic kaf/ye forms of كافه (ك is U+0643, ه is U+0647).
        self.assertEqual(self._codes("\u0643\u0627\u0641\u0647"), {"K-500"})

    def test_zwnj_variants_are_matched(self):
        # Stored text has a ZWNJ; the query omits it (and vice-versa).
        self.assertEqual(self._codes("میخواهم"), {"Z-600"})
        self.assertEqual(self._codes("می\u200cخواهم"), {"Z-600"})

    def test_dissimilar_term_is_not_matched(self):
        # خانه is far below 70% similarity to آپارتمان دو خواب.
        self.assertNotIn("A-100", self._codes("خانه"))

    def test_empty_query_returns_everything_unchanged(self):
        qs = apply_fuzzy_search(Property.objects.all(), "", self.FIELDS)
        codes = set(qs.values_list("internal_code", flat=True))
        self.assertEqual(len(codes), Property.objects.count())
        self.assertEqual(codes, set(Property.objects.values_list("internal_code", flat=True)))

    def test_multi_word_query_is_token_aware(self):
        # "خواب" matches the token inside "آپارتمان دو خواب".
        self.assertEqual(self._codes("خواب"), {"A-100"})

    def test_internal_code_search_works(self):
        self.assertEqual(self._codes("V-200"), {"V-200"})

    def test_neighborhood_search_works(self):
        self.apartment.neighborhood = "زعفرانیه"
        self.apartment.save(update_fields=["neighborhood"])
        qs = apply_fuzzy_search(
            Property.objects.all(),
            "زعفرانیه",
            ["title", "internal_code", "address", "neighborhood"],
        )
        self.assertIn("A-100", set(qs.values_list("internal_code", flat=True)))

    def test_partial_and_typo_villa_matches_both(self):
        # Searching "ویلا" should return both "ویلا ساحلی" and similar villa listings
        v1 = _make_property("ویلا", "V-201", self.agent)
        v2 = _make_property("ویلا تریبلکس", "V-202", self.agent)
        codes = self._codes("ویلا")
        self.assertIn("V-201", codes)
        self.assertIn("V-202", codes)

        # Searching "ویا" (missing 'ل') should still match both "ویلا" and "ویلا تریبلکس"
        typo_codes = self._codes("ویا")
        self.assertIn("V-201", typo_codes)
        self.assertIn("V-202", typo_codes)

    def test_internal_codes_match_exactly_never_fuzzy(self):
        """Codes are identifiers: a fuzzy match must never surface a
        different code whose trigrams happen to be close (V-201 vs V-202)."""
        _make_property("ویلا", "V-201", self.agent)
        _make_property("ویلا تریبلکس", "V-202", self.agent)
        self.assertEqual(self._codes("V-201"), {"V-201"})
        self.assertEqual(self._codes("V-202"), {"V-202"})
        # Prefix search still works for codes (V-200 also exists in the
        # shared test data).
        self.assertEqual(self._codes("V-20"), {"V-200", "V-201", "V-202"})

    def test_word_boundary_noise_is_rejected(self):
        """A query must not leak through a *different* word of a field just
        because trigrams overlap («خواب» vs «می‌خواهم», «نیاوران» vs
        «تهران»)."""
        self.assertEqual(self._codes("خواب"), {"A-100"})

        tehran_only = _make_property("برج", "T-1", self.agent, address="تهران")
        _make_property("برج نیاوران", "T-2", self.agent, neighborhood="نیاوران")
        fields = ["title", "internal_code", "address", "neighborhood"]
        qs = apply_fuzzy_search(Property.objects.all(), "نیاوران", fields)
        codes = set(qs.values_list("internal_code", flat=True))
        self.assertEqual(codes, {"T-2"})
        self.assertIn(tehran_only.id, Property.objects.values_list("id", flat=True))


class PropertySearchAPITests(TestCase):
    """End-to-end checks against /properties/api/properties/?q=…."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="ps-admin", password="pw", role="ADMIN")
        cls.agent = User.objects.create_user(username="ps-agent", password="pw", role="AGENT")
        cls.other = User.objects.create_user(username="ps-other", password="pw", role="AGENT")
        # Enough rows to exercise pagination (page_size is 20).
        for i in range(30):
            _make_property(f"آپارتمان شماره {i}", f"AP-{i:03d}", cls.agent)
        # A property belonging to a different agent, to test role scoping.
        _make_property("ویلا اختصاصی", "OTHER-1", cls.other, property_type="VILLA")

    def setUp(self):
        self.client.force_login(self.admin)

    def _search(self, query, **params):
        resp = self.client.get("/properties/api/properties/", {**params, "q": query})
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        data = resp.json()
        return data

    def test_search_by_neighborhood_via_api(self):
        _make_property("برج باغ", "NB-1", self.agent, neighborhood="الهیه")
        data = self._search("الهیه", page_size=100)
        codes = {row["internalCode"] for row in data["results"]}
        self.assertIn("NB-1", codes)

    def test_fuzzy_match_is_returned(self):
        # Pull every match into one page so presence is checked, not ordering.
        data = self._search("آپارتمان", page_size=100)
        self.assertEqual(data["count"], 30)
        codes = {row["internalCode"] for row in data["results"]}
        self.assertIn("AP-000", codes)

    def test_typo_is_tolerated(self):
        data = self._search("اپارتمان", page_size=100)
        codes = {row["internalCode"] for row in data["results"]}
        self.assertIn("AP-000", codes)

    def test_dissimilar_term_matches_nothing(self):
        data = self._search("خرید زمین کشاورزی")
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])

    def test_pagination_integrity(self):
        # Every matched row is returned across pages, and no non-match leaks in.
        data = self._search("آپارتمان", page_size=7)
        self.assertEqual(data["count"], 30)
        self.assertEqual(len(data["results"]), 7)

        collected = set()
        collected |= {row["internalCode"] for row in data["results"]}
        next_url = data["next"]
        while next_url:
            page = self.client.get(next_url).json()
            collected |= {row["internalCode"] for row in page["results"]}
            next_url = page["next"]

        self.assertEqual(collected, {f"AP-{i:03d}" for i in range(30)})

    def test_relevance_ties_order_deterministically(self):
        """When many rows share the same relevance score the order must be
        deterministic (newest id first), otherwise page boundaries shuffle
        between requests and rows get skipped or repeated."""
        data = self._search("آپارتمان", page_size=7)
        codes = [row["internalCode"] for row in data["results"]]
        self.assertEqual(codes, [f"AP-{i:03d}" for i in range(29, 22, -1)])

    def test_consultant_only_sees_their_own_rows(self):
        self.client.force_login(self.agent)
        data = self._search("آپارتمان", page_size=100)
        codes = {row["internalCode"] for row in data["results"]}
        self.assertIn("AP-000", codes)
        self.assertNotIn("OTHER-1", codes)

        # A free-text query that would fuzzy-match the other agent's title
        # must still not leak their row through.
        self.client.force_login(self.other)
        other_data = self._search("ویلا", page_size=100)
        other_codes = {row["internalCode"] for row in other_data["results"]}
        self.assertIn("OTHER-1", other_codes)


class ListingSearchAPITests(TestCase):
    """End-to-end checks against /listings/api/listings/?q=…."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="ls-admin", password="pw", role="ADMIN")
        cls.agent = User.objects.create_user(username="ls-agent", password="pw", role="AGENT")
        cls.apartment = _make_property("آپارتمان مرکز شهر", "LC-1", cls.agent)
        cls.villa = _make_property("ویلا جنگلی", "LC-2", cls.agent, property_type="VILLA")
        Listing.objects.create(
            property=cls.apartment,
            title="فروش آپارتمان لوکس",
            publish_channel="WEBSITE",
            created_by=cls.agent,
        )
        Listing.objects.create(
            property=cls.villa,
            title="اجاره ویلا شمال",
            publish_channel="WEBSITE",
            created_by=cls.agent,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _titles(self, query):
        resp = self.client.get("/listings/api/listings/", {"q": query})
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return {row["title"] for row in resp.json()["results"]}

    def test_match_by_listing_title(self):
        # A multi-word query that is an exact word sequence of the listing title.
        self.assertEqual(self._titles("فروش آپارتمان"), {"فروش آپارتمان لوکس"})

    def test_match_through_property_title(self):
        # "ویلا" is not in the listing title, only in the linked property title.
        self.assertEqual(self._titles("ویلا"), {"اجاره ویلا شمال"})

    def test_match_through_property_internal_code(self):
        self.assertEqual(self._titles("LC-1"), {"فروش آپارتمان لوکس"})
        # Symmetric: the sibling code must resolve to its own listing and
        # never leak through fuzzy matching (LC-1 vs LC-2 share trigrams).
        self.assertEqual(self._titles("LC-2"), {"اجاره ویلا شمال"})

    def test_match_through_neighborhood(self):
        self.apartment.neighborhood = "نیاوران"
        self.apartment.save(update_fields=["neighborhood"])
        self.assertEqual(self._titles("نیاوران"), {"فروش آپارتمان لوکس"})

    def test_match_by_numeric_listing_id(self):
        listing = Listing.objects.get(title="فروش آپارتمان لوکس")
        self.assertEqual(self._titles(str(listing.id)), {"فروش آپارتمان لوکس"})
        self.assertEqual(self._titles("۱۲۳۴۵۶۷۸۹"), set())

    def test_typo_is_tolerated(self):
        # Missing hamza on the alef: اپارتمان vs آپارتمان.
        self.assertEqual(self._titles("اپارتمان لوکس"), {"فروش آپارتمان لوکس"})
