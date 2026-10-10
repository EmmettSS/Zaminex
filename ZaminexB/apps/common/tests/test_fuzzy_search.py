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
    def test_arabic_letters_unify_to_persian(self):
        self.assertEqual(normalize_persian_text("\u0643"), "ک")
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
    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(username="fs-agent", password="pw", role="AGENT")
        cls.apartment = _make_property("آپارتمان دو خواب", "ZF_9100", cls.agent)
        cls.villa = _make_property("ویلا ساحلی", "ZF_9200", cls.agent, property_type="VILLA")
        cls.office = _make_property("دفتر کار مرکزی", "ZF_9300", cls.agent, property_type="OFFICE", deal_type="RENT")
        cls.consultancy = _make_property("مرکز مشاور املاک", "ZF_9400", cls.agent)
        cls.cafe = _make_property("کافه", "ZF_9500", cls.agent)
        cls.zwnj = _make_property("می\u200cخواهم", "ZF_9600", cls.agent)

    FIELDS = ["title", "internal_code", "address"]

    def _codes(self, query):
        qs = apply_fuzzy_search(Property.objects.all(), query, self.FIELDS)
        return set(qs.values_list("internal_code", flat=True))

    def test_exact_persian_term_is_matched(self):
        self.assertEqual(self._codes("آپارتمان"), {"ZF_9100"})

    def test_typo_is_tolerated(self):
        self.assertEqual(self._codes("اپارتمان"), {"ZF_9100"})

    def test_transposed_characters_are_tolerated(self):
        self.assertEqual(self._codes("مشاهر"), {"ZF_9400"})

    def test_arabic_variant_letters_are_matched(self):
        self.assertEqual(self._codes("\u0643\u0627\u0641\u0647"), {"ZF_9500"})

    def test_zwnj_variants_are_matched(self):
        self.assertEqual(self._codes("میخواهم"), {"ZF_9600"})
        self.assertEqual(self._codes("می\u200cخواهم"), {"ZF_9600"})

    def test_dissimilar_term_is_not_matched(self):
        self.assertNotIn("ZF_9100", self._codes("خانه"))

    def test_empty_query_returns_everything_unchanged(self):
        qs = apply_fuzzy_search(Property.objects.all(), "", self.FIELDS)
        codes = set(qs.values_list("internal_code", flat=True))
        self.assertEqual(len(codes), Property.objects.count())
        self.assertEqual(codes, set(Property.objects.values_list("internal_code", flat=True)))

    def test_multi_word_query_is_token_aware(self):
        self.assertEqual(self._codes("خواب"), {"ZF_9100"})

    def test_internal_code_search_works(self):
        self.assertEqual(self._codes("ZF_9200"), {"ZF_9200"})

    def test_neighborhood_search_works(self):
        self.apartment.neighborhood = "زعفرانیه"
        self.apartment.save(update_fields=["neighborhood"])
        qs = apply_fuzzy_search(
            Property.objects.all(),
            "زعفرانیه",
            ["title", "internal_code", "address", "neighborhood"],
        )
        self.assertIn("ZF_9100", set(qs.values_list("internal_code", flat=True)))

    def test_partial_and_typo_villa_matches_both(self):
        v1 = _make_property("ویلا", "ZF_9201", self.agent)
        v2 = _make_property("ویلا تریبلکس", "ZF_9202", self.agent)
        codes = self._codes("ویلا")
        self.assertIn("ZF_9201", codes)
        self.assertIn("ZF_9202", codes)

        typo_codes = self._codes("ویا")
        self.assertIn("ZF_9201", typo_codes)
        self.assertIn("ZF_9202", typo_codes)

    def test_internal_codes_match_exactly_never_fuzzy(self):
        _make_property("ویلا", "ZF_9201", self.agent)
        _make_property("ویلا تریبلکس", "ZF_9202", self.agent)
        self.assertEqual(self._codes("ZF_9201"), {"ZF_9201"})
        self.assertEqual(self._codes("ZF_9202"), {"ZF_9202"})
        self.assertEqual(self._codes("ZF_920"), {"ZF_9200", "ZF_9201", "ZF_9202"})

    def test_word_boundary_noise_is_rejected(self):
        self.assertEqual(self._codes("خواب"), {"ZF_9100"})

        tehran_only = _make_property("برج", "ZF_9701", self.agent, address="تهران")
        _make_property("برج نیاوران", "ZF_9702", self.agent, neighborhood="نیاوران")
        fields = ["title", "internal_code", "address", "neighborhood"]
        qs = apply_fuzzy_search(Property.objects.all(), "نیاوران", fields)
        codes = set(qs.values_list("internal_code", flat=True))
        self.assertEqual(codes, {"ZF_9702"})
        self.assertIn(tehran_only.id, Property.objects.values_list("id", flat=True))


class PropertySearchAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="ps-admin", password="pw", role="ADMIN")
        cls.agent = User.objects.create_user(username="ps-agent", password="pw", role="AGENT")
        cls.other = User.objects.create_user(username="ps-other", password="pw", role="AGENT")
        
        for i in range(30):
            _make_property(f"آپارتمان شماره {i}", f"ZF_90{i:02d}", cls.agent)
            
        _make_property("ویلا اختصاصی", "ZF_9090", cls.other, property_type="VILLA")

    def setUp(self):
        self.client.force_login(self.admin)

    def _search(self, query, **params):
        resp = self.client.get("/properties/api/properties/", {**params, "q": query})
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        data = resp.json()
        return data

    def test_search_by_neighborhood_via_api(self):
        _make_property("برج باغ", "ZF_9080", self.agent, neighborhood="الهیه")
        data = self._search("الهیه", page_size=100)
        codes = {row["internalCode"] for row in data["results"]}
        self.assertIn("ZF_9080", codes)

    def test_fuzzy_match_is_returned(self):
        data = self._search("آپارتمان", page_size=100)
        self.assertEqual(data["count"], 30)
        codes = {row["internalCode"] for row in data["results"]}
        self.assertIn("ZF_9000", codes)

    def test_typo_is_tolerated(self):
        data = self._search("اپارتمان", page_size=100)
        codes = {row["internalCode"] for row in data["results"]}
        self.assertIn("ZF_9000", codes)

    def test_dissimilar_term_matches_nothing(self):
        data = self._search("خرید زمین کشاورزی")
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])

    def test_pagination_integrity(self):
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

        self.assertEqual(collected, {f"ZF_90{i:02d}" for i in range(30)})

    def test_relevance_ties_order_deterministically(self):
        data = self._search("آپارتمان", page_size=7)
        codes = [row["internalCode"] for row in data["results"]]
        self.assertEqual(codes, [f"ZF_90{i:02d}" for i in range(29, 22, -1)])

    def test_consultant_only_sees_their_own_rows(self):
        self.client.force_login(self.agent)
        data = self._search("آپارتمان", page_size=100)
        codes = {row["internalCode"] for row in data["results"]}
        self.assertIn("ZF_9000", codes)
        self.assertNotIn("ZF_9090", codes)
        self.client.force_login(self.other)
        other_data = self._search("ویلا", page_size=100)
        other_codes = {row["internalCode"] for row in other_data["results"]}
        self.assertIn("ZF_9090", other_codes)


class ListingSearchAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="ls-admin", password="pw", role="ADMIN")
        cls.agent = User.objects.create_user(username="ls-agent", password="pw", role="AGENT")
        cls.apartment = _make_property("آپارتمان مرکز شهر", "ZF_9601", cls.agent)
        cls.villa = _make_property("ویلا جنگلی", "ZF_9602", cls.agent, property_type="VILLA")
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
        self.assertEqual(self._titles("فروش آپارتمان"), {"فروش آپارتمان لوکس"})

    def test_match_through_property_title(self):
        self.assertEqual(self._titles("ویلا"), {"اجاره ویلا شمال"})

    def test_match_through_property_internal_code(self):
        self.assertEqual(self._titles("ZF_9601"), {"فروش آپارتمان لوکس"})
        self.assertEqual(self._titles("ZF_9602"), {"اجاره ویلا شمال"})

    def test_match_through_neighborhood(self):
        self.apartment.neighborhood = "نیاوران"
        self.apartment.save(update_fields=["neighborhood"])
        self.assertEqual(self._titles("نیاوران"), {"فروش آپارتمان لوکس"})

    def test_match_by_numeric_listing_id(self):
        listing = Listing.objects.get(title="فروش آپارتمان لوکس")
        self.assertEqual(self._titles(str(listing.id)), {"فروش آپارتمان لوکس"})
        self.assertEqual(self._titles("۱۲۳۴۵۶۷۸۹"), set())

    def test_typo_is_tolerated(self):
        self.assertEqual(self._titles("اپارتمان لوکس"), {"فروش آپارتمان لوکس"})
