"""Tests for the `seed_basics` and `link_properties_to_basics` commands."""

import io

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.basics.models import Attribute, DealType, PropertyType, PropertyUsage
from apps.listings.models import Listing
from apps.properties.models import Property

User = get_user_model()


class SeedBasicsTests(TestCase):
    def test_seeding_creates_the_starter_catalogue(self):
        call_command("seed_basics", stdout=io.StringIO())

        self.assertEqual(
            set(PropertyUsage.objects.values_list("name", flat=True)),
            {"residential", "commercial", "office"},
            "the three usages the client asked for",
        )
        self.assertTrue(PropertyType.objects.filter(name="apartment").exists())
        self.assertTrue(DealType.objects.filter(name="mortgage_rent").exists())
        self.assertTrue(Attribute.objects.filter(name="rooms", is_core=True).exists())

    def test_rooms_reaches_apartment_but_not_land(self):
        call_command("seed_basics", stdout=io.StringIO())

        apartment = PropertyType.objects.get(name="apartment")
        land = PropertyType.objects.get(name="land")

        self.assertIn(
            "rooms", {link.attribute.name for link in apartment.attribute_links.all()}
        )
        self.assertNotIn(
            "rooms", {link.attribute.name for link in land.attribute_links.all()}
        )

    def test_running_it_twice_changes_nothing(self):
        call_command("seed_basics", stdout=io.StringIO())
        counts = (
            PropertyUsage.objects.count(),
            PropertyType.objects.count(),
            DealType.objects.count(),
            Attribute.objects.count(),
        )

        call_command("seed_basics", stdout=io.StringIO())

        self.assertEqual(
            counts,
            (
                PropertyUsage.objects.count(),
                PropertyType.objects.count(),
                DealType.objects.count(),
                Attribute.objects.count(),
            ),
        )

    def test_locally_edited_labels_survive_a_re_run(self):
        call_command("seed_basics", stdout=io.StringIO())
        apartment = PropertyType.objects.get(name="apartment")
        apartment.display_name = "آپارتمان مسکونی"
        apartment.save()

        call_command("seed_basics", stdout=io.StringIO())

        apartment.refresh_from_db()
        self.assertEqual(apartment.display_name, "آپارتمان مسکونی")

    def test_force_resets_labels_to_the_defaults(self):
        call_command("seed_basics", stdout=io.StringIO())
        apartment = PropertyType.objects.get(name="apartment")
        apartment.display_name = "دستکاری شده"
        apartment.save()

        call_command("seed_basics", "--force", stdout=io.StringIO())

        apartment.refresh_from_db()
        self.assertEqual(apartment.display_name, "آپارتمان")


class LinkPropertiesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(
            username="link-agent", password="pw", role="AGENT"
        )

    def _property(self, code, property_type, deal_type="SALE"):
        return Property.objects.create(
            title=f"ملک {code}",
            internal_code=code,
            consultant=self.agent,
            property_type=property_type,
            deal_type=deal_type,
            price=1_000,
            area=100,
            address="آدرس",
            neighborhood="محله",
        )

    def test_it_refuses_to_run_before_seeding(self):
        self._property("L-0", "APARTMENT")
        with self.assertRaises(CommandError):
            call_command("link_properties_to_basics", stdout=io.StringIO())

    def test_legacy_types_are_mapped_to_reference_rows(self):
        prop = self._property("L-1", "APARTMENT")
        call_command("seed_basics", stdout=io.StringIO())
        call_command("link_properties_to_basics", stdout=io.StringIO())

        prop.refresh_from_db()
        self.assertEqual(prop.property_type_ref.name, "apartment")
        self.assertEqual(prop.property_usage.name, "residential")

    def test_the_usage_follows_the_type(self):
        prop = self._property("L-2", "SHOP")
        call_command("seed_basics", stdout=io.StringIO())
        call_command("link_properties_to_basics", stdout=io.StringIO())

        prop.refresh_from_db()
        self.assertEqual(prop.property_usage.name, "commercial")

    def test_listings_inherit_the_deal_type_from_their_property(self):
        prop = self._property("L-3", "APARTMENT", deal_type="RENT")
        listing = Listing.objects.create(
            property=prop,
            title="آگهی",
            publish_channel="WEBSITE",
            created_by=self.agent,
        )

        call_command("seed_basics", stdout=io.StringIO())
        call_command("link_properties_to_basics", stdout=io.StringIO())

        listing.refresh_from_db()
        self.assertEqual(
            listing.deal_type.name,
            "mortgage_rent",
            "RENT maps to رهن و اجاره",
        )

    def test_dry_run_writes_nothing(self):
        prop = self._property("L-4", "APARTMENT")
        call_command("seed_basics", stdout=io.StringIO())
        call_command("link_properties_to_basics", "--dry-run", stdout=io.StringIO())

        prop.refresh_from_db()
        self.assertIsNone(prop.property_type_ref)

    def test_running_it_twice_is_harmless(self):
        prop = self._property("L-5", "VILLA")
        call_command("seed_basics", stdout=io.StringIO())
        call_command("link_properties_to_basics", stdout=io.StringIO())
        prop.refresh_from_db()
        first = prop.property_type_ref_id
        self.assertIsNotNone(first, "the first run should have linked it")

        call_command("link_properties_to_basics", stdout=io.StringIO())

        prop.refresh_from_db()
        self.assertEqual(prop.property_type_ref_id, first)

    def test_an_existing_link_is_never_overwritten(self):
        prop = self._property("L-6", "APARTMENT")
        call_command("seed_basics", stdout=io.StringIO())

        villa = PropertyType.objects.get(name="villa")
        prop.property_type_ref = villa
        prop.save()

        call_command("link_properties_to_basics", stdout=io.StringIO())

        prop.refresh_from_db()
        self.assertEqual(
            prop.property_type_ref.name,
            "villa",
            "a manual correction must not be reverted",
        )
