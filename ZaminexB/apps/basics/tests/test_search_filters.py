"""Tests for the dynamic search filters (phase 7).

The `*_search_attributes` tables and the schema endpoint shipped in phase 2, but
nothing could actually *filter* by a dynamic attribute. These cover the
`attr_*` query parameters and the corrected price range.
"""

import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.basics.models import (
    Attribute,
    AttributeOption,
    DealType,
    PropertyType,
    PropertyTypeSearchAttribute,
)
from apps.listings.models import Listing
from apps.properties.models import Property, PropertyAttributeValue

User = get_user_model()


class AttributeFilterTests(TestCase):
    """`?attr_<name>=…` narrows on the typed EAV column."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="flt-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="flt-agent", password="pw", role="AGENT"
        )
        cls.apartment = PropertyType.objects.get(name="apartment")
        cls.floors = Attribute.objects.get(name="total_floors")
        cls.parking = Attribute.objects.get(name="parking")
        cls.document = Attribute.objects.get(name="document_type")

        # three properties with deliberately different values
        cls.rows = {}
        for code, floors, parking, area in [
            ("F-1", 5, True, 80),
            ("F-2", 12, False, 120),
            ("F-3", 25, True, 200),
        ]:
            prop = Property.objects.create(
                title=f"ملک {code}",
                internal_code=code,
                consultant=cls.agent,
                property_type="APARTMENT",
                property_type_ref=cls.apartment,
                area=area,
                address="آدرس",
                neighborhood="محله",
            )
            for attribute, value in ((cls.floors, floors), (cls.parking, parking)):
                row = PropertyAttributeValue(property=prop, attribute=attribute)
                row.set_value(value)
                row.save()
            cls.rows[code] = prop

    def setUp(self):
        self.client.force_login(self.admin)

    def _codes(self, query=""):
        response = self.client.get(f"/properties/api/properties/{query}")
        self.assertEqual(response.status_code, 200, response.content[:300])
        return {row["internalCode"] for row in response.json()["results"]}

    def test_a_numeric_minimum(self):
        self.assertEqual(self._codes("?attr_total_floors_min=10"), {"F-2", "F-3"})

    def test_a_numeric_maximum(self):
        self.assertEqual(self._codes("?attr_total_floors_max=12"), {"F-1", "F-2"})

    def test_a_numeric_range(self):
        self.assertEqual(
            self._codes("?attr_total_floors_min=10&attr_total_floors_max=20"), {"F-2"}
        )

    def test_the_comparison_is_numeric_not_textual(self):
        """A string compare would place 5 above 25."""
        self.assertEqual(self._codes("?attr_total_floors_min=20"), {"F-3"})

    def test_a_boolean_filter(self):
        self.assertEqual(self._codes("?attr_parking=true"), {"F-1", "F-3"})
        self.assertEqual(self._codes("?attr_parking=false"), {"F-2"})

    def test_two_filters_are_combined_with_and(self):
        self.assertEqual(
            self._codes("?attr_parking=true&attr_total_floors_min=10"), {"F-3"}
        )

    def test_conditions_apply_to_the_same_attribute_row(self):
        """A min and a max must bracket one value, not be satisfied separately."""
        self.assertEqual(
            self._codes("?attr_total_floors_min=24&attr_total_floors_max=26"), {"F-3"}
        )

    def test_a_core_attribute_filters_on_its_real_column(self):
        self.assertEqual(self._codes("?attr_area_min=120"), {"F-2", "F-3"})

    def test_a_select_filter_matches_the_stored_option(self):
        value = PropertyAttributeValue(
            property=self.rows["F-1"], attribute=self.document
        )
        value.set_value("single_deed")
        value.save()

        self.assertEqual(self._codes("?attr_document_type=single_deed"), {"F-1"})

    def test_an_unknown_attribute_is_ignored(self):
        """A stale bookmark should widen the results, not error."""
        self.assertEqual(self._codes("?attr_not_a_field=1"), {"F-1", "F-2", "F-3"})

    def test_an_unparseable_value_is_ignored(self):
        self.assertEqual(
            self._codes("?attr_total_floors_min=abc"), {"F-1", "F-2", "F-3"}
        )

    def test_an_empty_value_is_ignored(self):
        self.assertEqual(self._codes("?attr_parking="), {"F-1", "F-2", "F-3"})

    def test_results_are_not_duplicated_by_the_join(self):
        codes = [
            row["internalCode"]
            for row in self.client.get(
                "/properties/api/properties/?attr_parking=true"
            ).json()["results"]
        ]
        self.assertEqual(len(codes), len(set(codes)))

    def test_a_consultant_only_sees_their_own_matches(self):
        other = User.objects.create_user(username="flt-other", password="pw", role="AGENT")
        self.client.force_login(other)
        self.assertEqual(self._codes("?attr_parking=true"), set())

    def test_scoping_to_a_property_type(self):
        villa = PropertyType.objects.get(name="villa")
        Property.objects.create(
            title="ویلا",
            internal_code="F-4",
            consultant=self.agent,
            property_type="VILLA",
            property_type_ref=villa,
            area=300,
            address="آدرس",
            neighborhood="محله",
        )
        self.assertNotIn("F-4", self._codes(f"?propertyTypeRef={self.apartment.pk}"))
        self.assertIn("F-4", self._codes(f"?propertyTypeRef={villa.pk}"))


class PriceFilterTests(TestCase):
    """The range must follow the listing price, like the reported one."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="pf-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="pf-agent", password="pw", role="AGENT"
        )
        sale = DealType.objects.get(name="sale")

        for code, price in [("P-1", 1_000_000_000), ("P-2", 5_000_000_000)]:
            prop = Property.objects.create(
                title=f"ملک {code}",
                internal_code=code,
                consultant=cls.agent,
                property_type="APARTMENT",
                area=100,
                address="آدرس",
                neighborhood="محله",
            )
            Listing.objects.create(
                property=prop,
                title="آگهی",
                publish_channel="WEBSITE",
                created_by=cls.agent,
                deal_type=sale,
                sale_price=price,
            )

        # priced the old way, to prove the fallback still filters
        Property.objects.create(
            title="قدیمی",
            internal_code="P-3",
            consultant=cls.agent,
            property_type="APARTMENT",
            price=9_000_000_000,
            area=100,
            address="آدرس",
            neighborhood="محله",
        )
        # no price at all
        Property.objects.create(
            title="بدون قیمت",
            internal_code="P-4",
            consultant=cls.agent,
            property_type="APARTMENT",
            area=100,
            address="آدرس",
            neighborhood="محله",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _codes(self, query):
        response = self.client.get(f"/properties/api/properties/{query}")
        self.assertEqual(response.status_code, 200)
        return {row["internalCode"] for row in response.json()["results"]}

    def test_a_minimum_uses_the_listing_price(self):
        """This matched nothing while the filter read the legacy column."""
        self.assertEqual(self._codes("?priceMin=2000000000"), {"P-2", "P-3"})

    def test_a_maximum_uses_the_listing_price(self):
        self.assertEqual(self._codes("?priceMax=2000000000"), {"P-1"})

    def test_a_range(self):
        self.assertEqual(
            self._codes("?priceMin=2000000000&priceMax=6000000000"), {"P-2"}
        )

    def test_a_property_without_a_price_is_excluded(self):
        """Zero would make it match every "from" filter."""
        self.assertNotIn("P-4", self._codes("?priceMin=1"))

    def test_the_legacy_column_still_participates(self):
        self.assertIn("P-3", self._codes("?priceMin=8000000000"))


class SearchSchemaTests(TestCase):
    """What drives the filter bar."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.agent = User.objects.create_user(
            username="ss-agent", password="pw", role="AGENT"
        )
        cls.admin = User.objects.create_user(
            username="ss-admin", password="pw", role="ADMIN"
        )

    def setUp(self):
        self.client.force_login(self.agent)

    def test_each_type_offers_its_own_filters(self):
        apartment = self.client.get(
            "/basics/api/schema/search/?propertyType=apartment"
        ).json()["propertyFilters"]
        land = self.client.get(
            "/basics/api/schema/search/?propertyType=land"
        ).json()["propertyFilters"]

        self.assertIn("rooms", {f["name"] for f in apartment})
        self.assertNotIn("rooms", {f["name"] for f in land})

    def test_a_filter_carries_what_the_ui_needs_to_render_it(self):
        filters = self.client.get(
            "/basics/api/schema/search/?propertyType=apartment"
        ).json()["propertyFilters"]
        floors = next(f for f in filters if f["name"] == "floor")

        self.assertEqual(floors["dataType"], "integer")
        self.assertEqual(floors["filterType"], "range")
        self.assertIn("displayName", floors)

    def test_select_filters_carry_their_options(self):
        land = PropertyType.objects.get(name="land")
        document = Attribute.objects.get(name="document_type")
        PropertyTypeSearchAttribute.objects.update_or_create(
            property_type=land, attribute=document, defaults={"sort_order": 99}
        )

        filters = self.client.get(
            "/basics/api/schema/search/?propertyType=land"
        ).json()["propertyFilters"]
        doc = next(f for f in filters if f["name"] == "document_type")
        self.assertGreater(len(doc["options"]), 0)

    def test_a_deactivated_search_binding_disappears(self):
        apartment = PropertyType.objects.get(name="apartment")
        PropertyTypeSearchAttribute.objects.filter(
            property_type=apartment, attribute__name="parking"
        ).update(is_active=False)

        filters = self.client.get(
            "/basics/api/schema/search/?propertyType=apartment"
        ).json()["propertyFilters"]
        self.assertNotIn("parking", {f["name"] for f in filters})

    def test_filters_arrive_in_the_configured_order(self):
        filters = self.client.get(
            "/basics/api/schema/search/?propertyType=apartment"
        ).json()["propertyFilters"]
        orders = [float(f["sortOrder"]) for f in filters]
        self.assertEqual(orders, sorted(orders))
