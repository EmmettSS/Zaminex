"""End-to-end tests for what the wizards now send and receive (phase 3).

Covers the two changes the client asked for:

* a property is created without a price or a deal type, carrying whatever
  custom fields its property type defines;
* price and deal type belong to the listing, so one property can be advertised
  for sale and for rent at the same time.
"""

import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.basics.models import Attribute, DealType, PropertyType
from apps.listings.models import Listing
from apps.properties.models import Property

User = get_user_model()


class PropertyWizardPayloadTests(TestCase):
    """The exact shape AddPropertyWizard posts."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="wiz-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="wiz-agent", password="pw", role="AGENT"
        )
        cls.apartment = PropertyType.objects.get(name="apartment")
        cls.land = PropertyType.objects.get(name="land")

    def setUp(self):
        self.client.force_login(self.admin)

    def _payload(self, **overrides):
        payload = {
            "title": "آپارتمان تست",
            "internalCode": "WIZ-1",
            "propertyTypeRef": self.apartment.pk,
            "area": 145,
            "beds": 3,
            "district": "مرکزی",
            "fullAddress": "تهران",
            "consultant": self.agent.pk,
        }
        payload.update(overrides)
        return payload

    def test_a_property_is_created_without_a_price(self):
        """Price moved to the listing, so it must no longer be required."""
        response = self.client.post(
            "/properties/api/properties/", self._payload(), content_type="application/json"
        )
        self.assertEqual(response.status_code, 201, response.content[:400])

        prop = Property.objects.get(internal_code="WIZ-1")
        self.assertIsNone(prop.price)

    def test_the_legacy_type_column_is_kept_in_sync(self):
        """Existing readers still use `property_type`, so it must stay correct."""
        self.client.post(
            "/properties/api/properties/", self._payload(), content_type="application/json"
        )
        prop = Property.objects.get(internal_code="WIZ-1")

        self.assertEqual(prop.property_type_ref, self.apartment)
        self.assertEqual(prop.property_type, "APARTMENT")

    def test_the_usage_is_derived_from_the_type(self):
        self.client.post(
            "/properties/api/properties/", self._payload(), content_type="application/json"
        )
        prop = Property.objects.get(internal_code="WIZ-1")
        self.assertEqual(prop.property_usage.name, "residential")

    def test_custom_fields_are_stored_and_returned(self):
        response = self.client.post(
            "/properties/api/properties/",
            self._payload(
                attributes={
                    "total_floors": 10,
                    "parking": True,
                    "document_type": "single_deed",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])

        body = response.json()
        self.assertEqual(body["attributes"]["total_floors"], 10)
        self.assertIs(body["attributes"]["parking"], True)
        self.assertEqual(body["attributes"]["document_type"], "single_deed")

        labels = {d["displayName"]: d["displayValue"] for d in body["attributeDetails"]}
        self.assertEqual(labels["پارکینگ"], "بله")
        self.assertEqual(labels["نوع سند"], "تک برگ")

    def test_an_attribute_of_another_type_is_rejected(self):
        """Land has no `rooms`, so sending a land-only field for a flat fails."""
        response = self.client.post(
            "/properties/api/properties/",
            self._payload(attributes={"not_a_real_field": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("attributes", response.json())

    def test_core_fields_must_not_be_sent_as_custom_fields(self):
        response = self.client.post(
            "/properties/api/properties/",
            self._payload(attributes={"area": 200}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_updating_replaces_a_value_and_clears_another(self):
        self.client.post(
            "/properties/api/properties/",
            self._payload(attributes={"total_floors": 10, "parking": True}),
            content_type="application/json",
        )
        prop = Property.objects.get(internal_code="WIZ-1")

        response = self.client.patch(
            f"/properties/api/properties/{prop.pk}/",
            {"attributes": {"total_floors": 15, "parking": None}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        attributes = response.json()["attributes"]
        self.assertEqual(attributes["total_floors"], 15)
        self.assertNotIn("parking", attributes, "a null value clears the field")

    def test_a_land_property_stores_its_own_field_set(self):
        response = self.client.post(
            "/properties/api/properties/",
            self._payload(
                internalCode="WIZ-LAND",
                propertyTypeRef=self.land.pk,
                attributes={"land_area": 500, "water_well": True},
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])
        self.assertEqual(response.json()["attributes"]["land_area"], 500)


class ListingPricingTests(TestCase):
    """Deal type and money live on the listing."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="price-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="price-agent", password="pw", role="AGENT"
        )
        cls.sale = DealType.objects.get(name="sale")
        cls.rent = DealType.objects.get(name="mortgage_rent")
        cls.property = Property.objects.create(
            title="ملک دو منظوره",
            internal_code="DUAL-1",
            consultant=cls.agent,
            property_type="APARTMENT",
            property_type_ref=PropertyType.objects.get(name="apartment"),
            area=120,
            address="تهران",
            neighborhood="مرکزی",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_a_sale_listing_records_a_sale_price(self):
        response = self.client.post(
            "/listings/api/listings/",
            {
                "title": "فروش",
                "property": self.property.pk,
                "publish_channel": "WEBSITE",
                "dealType": self.sale.pk,
                "salePrice": 18_000_000_000,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])

        body = response.json()
        self.assertEqual(body["dealTypeName"], "sale")
        self.assertEqual(int(float(body["salePrice"])), 18_000_000_000)
        self.assertIsNone(body["deposit"])

    def test_a_rental_listing_records_a_deposit_and_a_monthly_rent(self):
        response = self.client.post(
            "/listings/api/listings/",
            {
                "title": "رهن و اجاره",
                "property": self.property.pk,
                "publish_channel": "WEBSITE",
                "dealType": self.rent.pk,
                "deposit": 800_000_000,
                "monthlyRent": 45_000_000,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])

        body = response.json()
        self.assertEqual(int(float(body["deposit"])), 800_000_000)
        self.assertEqual(int(float(body["monthlyRent"])), 45_000_000)
        self.assertIsNone(body["salePrice"])

    def test_one_property_can_be_for_sale_and_for_rent_at_once(self):
        """The reason pricing had to leave the property record."""
        for payload in (
            {
                "title": "فروش",
                "property": self.property.pk,
                "publish_channel": "WEBSITE",
                "dealType": self.sale.pk,
                "salePrice": 18_000_000_000,
            },
            {
                "title": "اجاره",
                "property": self.property.pk,
                "publish_channel": "WEBSITE",
                "dealType": self.rent.pk,
                "deposit": 800_000_000,
                "monthlyRent": 45_000_000,
            },
        ):
            response = self.client.post(
                "/listings/api/listings/", payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 201, response.content[:400])

        listings = Listing.objects.filter(property=self.property)
        self.assertEqual(listings.count(), 2)
        self.assertEqual(
            {listing.deal_type.name for listing in listings},
            {"sale", "mortgage_rent"},
            "the same property carries two different deal types simultaneously",
        )

    def test_listing_custom_fields_are_stored(self):
        deposit_attr = Attribute.objects.create(
            name="commission",
            display_name="کمیسیون",
            data_type=Attribute.DataType.DECIMAL,
            entity=Attribute.Entity.LISTING,
        )
        response = self.client.post(
            "/listings/api/listings/",
            {
                "title": "با کمیسیون",
                "property": self.property.pk,
                "publish_channel": "WEBSITE",
                "dealType": self.sale.pk,
                "attributes": {"commission": "2.5"},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])
        self.assertEqual(float(response.json()["attributes"]["commission"]), 2.5)


class PricingMigrationTests(TestCase):
    """`move_pricing_to_listings` must not lose a recorded price."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.agent = User.objects.create_user(
            username="mig-agent", password="pw", role="AGENT"
        )

    def _property(self, code, deal_type, price):
        return Property.objects.create(
            title=f"ملک {code}",
            internal_code=code,
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type=deal_type,
            price=price,
            area=100,
            address="آدرس",
            neighborhood="محله",
        )

    def test_a_sale_price_lands_on_the_listing(self):
        prop = self._property("MIG-1", "SALE", 5_000_000_000)
        listing = Listing.objects.create(
            property=prop,
            title="آگهی",
            publish_channel="WEBSITE",
            created_by=self.agent,
            deal_type=DealType.objects.get(name="sale"),
        )

        call_command("move_pricing_to_listings", stdout=io.StringIO())

        listing.refresh_from_db()
        self.assertEqual(int(listing.sale_price), 5_000_000_000)

    def test_a_rental_price_becomes_the_deposit(self):
        prop = self._property("MIG-2", "RENT", 900_000_000)
        listing = Listing.objects.create(
            property=prop,
            title="آگهی",
            publish_channel="WEBSITE",
            created_by=self.agent,
            deal_type=DealType.objects.get(name="mortgage_rent"),
        )

        call_command("move_pricing_to_listings", stdout=io.StringIO())

        listing.refresh_from_db()
        self.assertEqual(int(listing.deposit), 900_000_000)
        self.assertIsNone(listing.sale_price)

    def test_a_property_with_no_listing_gets_one_so_the_price_survives(self):
        prop = self._property("MIG-3", "SALE", 7_000_000_000)

        call_command("move_pricing_to_listings", stdout=io.StringIO())

        listing = Listing.objects.get(property=prop)
        self.assertEqual(int(listing.sale_price), 7_000_000_000)
        self.assertEqual(listing.status, Listing.Status.DRAFT)

    def test_an_existing_price_is_never_overwritten(self):
        prop = self._property("MIG-4", "SALE", 5_000_000_000)
        listing = Listing.objects.create(
            property=prop,
            title="آگهی",
            publish_channel="WEBSITE",
            created_by=self.agent,
            deal_type=DealType.objects.get(name="sale"),
            sale_price=9_999,
        )

        call_command("move_pricing_to_listings", stdout=io.StringIO())

        listing.refresh_from_db()
        self.assertEqual(int(listing.sale_price), 9_999)

    def test_running_it_twice_changes_nothing(self):
        self._property("MIG-5", "SALE", 3_000_000_000)
        call_command("move_pricing_to_listings", stdout=io.StringIO())
        first = Listing.objects.count()

        call_command("move_pricing_to_listings", stdout=io.StringIO())

        self.assertEqual(Listing.objects.count(), first)


class NullPriceRobustnessTests(TestCase):
    """Metrics must cope with the price column now being nullable."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.agent = User.objects.create_user(
            username="null-agent", password="pw", role="AGENT"
        )
        cls.admin = User.objects.create_user(
            username="null-admin", password="pw", role="ADMIN"
        )
        Property.objects.create(
            title="بدون قیمت",
            internal_code="NULL-1",
            consultant=cls.agent,
            property_type="APARTMENT",
            area=100,
            address="آدرس",
            neighborhood="مشترک",
        )
        Property.objects.create(
            title="با قیمت",
            internal_code="NULL-2",
            consultant=cls.agent,
            property_type="APARTMENT",
            price=1_000_000_000,
            area=100,
            address="آدرس",
            neighborhood="مشترک",
        )

    def test_the_neighbourhood_average_ignores_properties_without_a_price(self):
        """Treating a missing price as zero would halve the average."""
        from apps.common.metrics import build_neighborhood_price_per_sqm_map

        averages = build_neighborhood_price_per_sqm_map()
        self.assertEqual(averages["مشترک"], 10_000_000)

    def test_listing_the_properties_still_works(self):
        self.client.force_login(self.admin)
        response = self.client.get("/properties/api/properties/")
        self.assertEqual(response.status_code, 200)

    def test_the_scope_report_still_works(self):
        self.client.force_login(self.admin)
        response = self.client.get("/api/reports/scope/")
        self.assertEqual(response.status_code, 200)
