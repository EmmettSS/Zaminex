"""Tests for the endpoints behind the attributes-management screen (phase 3).

The API existed since phase 2 but nothing consumed it; adding the panel exposed
three gaps that are covered here: options could be created but never removed,
and both attributes and options demanded a system key the UI has no way to ask
for.
"""

import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.basics.models import (
    Attribute,
    AttributeOption,
    DealType,
    DealTypeSearchAttribute,
    PropertyType,
    PropertyTypeAttribute,
    PropertyTypeSearchAttribute,
)
from apps.properties.models import Property, PropertyAttributeValue

User = get_user_model()


class AttributeCreationTests(TestCase):
    """The panel sends a Persian label and nothing else."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="attr-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="attr-agent", password="pw", role="AGENT"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_the_system_key_is_derived_from_the_label(self):
        response = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "جهت نما", "dataType": "text", "entity": "property"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertTrue(response.json()["name"], "a key should have been generated")

    def test_an_explicit_key_is_still_honoured(self):
        response = self.client.post(
            "/basics/api/attributes/",
            {"name": "custom_key", "displayName": "کلید دستی", "dataType": "text"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "custom_key")

    def test_a_duplicate_label_is_rejected(self):
        """Two attributes with one label are indistinguishable in the list."""
        self.client.post(
            "/basics/api/attributes/",
            {"displayName": "تکراری", "dataType": "text"},
            content_type="application/json",
        )
        response = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "تکراری", "dataType": "integer"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("displayName", response.json())

    def test_generated_keys_do_not_collide(self):
        """Distinct labels that slugify alike must still both save."""
        first = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "نما", "dataType": "text"},
            content_type="application/json",
        )
        Attribute.objects.filter(pk=first.json()["id"]).update(display_name="نمای الف")

        second = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "نما", "dataType": "text"},
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 201, second.content[:300])
        self.assertNotEqual(first.json()["name"], second.json()["name"])

    def test_a_consultant_cannot_create_an_attribute(self):
        self.client.force_login(self.agent)
        response = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "نفوذ", "dataType": "text"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_omitted_filter_type_defaults_to_something_searchable(self):
        text = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "جهت نمای سفارشی", "dataType": "text", "entity": "property"},
            content_type="application/json",
        )
        self.assertEqual(text.status_code, 201, text.content[:300])
        self.assertEqual(text.json()["filterType"], "exact")

        number = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "تعداد پارکینگ سفارشی", "dataType": "integer"},
            content_type="application/json",
        )
        self.assertEqual(number.status_code, 201, number.content[:300])
        self.assertEqual(number.json()["filterType"], "range")

        flag = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "انباری سفارشی", "dataType": "boolean"},
            content_type="application/json",
        )
        self.assertEqual(flag.status_code, 201, flag.content[:300])
        self.assertEqual(flag.json()["filterType"], "exists")

    def test_an_explicit_none_filter_is_honoured(self):
        response = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "یادداشت داخلی", "dataType": "text", "filterType": "none"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertEqual(response.json()["filterType"], "none")

    def test_a_facility_is_forced_to_boolean(self):
        response = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "سونا سفارشی", "dataType": "text", "isFacility": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        body = response.json()
        self.assertEqual(body["dataType"], "boolean")
        self.assertTrue(body["isFacility"])


class AttributeOptionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="opt-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="opt-agent", password="pw", role="AGENT"
        )
        cls.attribute = Attribute.objects.create(
            name="facade",
            display_name="نمای ساختمان",
            data_type=Attribute.DataType.SELECT,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _add(self, label):
        return self.client.post(
            f"/basics/api/attributes/{self.attribute.pk}/options/",
            {"displayName": label},
            content_type="application/json",
        )

    def test_an_option_key_is_derived_from_its_label(self):
        response = self._add("سنگ")
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertTrue(response.json()["value"])

    def test_a_duplicate_label_is_rejected(self):
        self._add("سنگ")
        response = self._add("سنگ")
        self.assertEqual(response.status_code, 400)

    def test_an_unused_option_can_be_deleted(self):
        option_id = self._add("آجر").json()["id"]
        response = self.client.delete(
            f"/basics/api/attributes/{self.attribute.pk}/options/{option_id}/"
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(AttributeOption.objects.filter(pk=option_id).exists())

    def test_an_option_in_use_cannot_be_deleted(self):
        """Removing it would leave stored records showing a raw key."""
        created = self._add("کامپوزیت").json()
        agent = User.objects.create_user(username="holder", password="pw", role="AGENT")
        prop = Property.objects.create(
            title="ملک",
            internal_code="OPT-1",
            consultant=agent,
            property_type="APARTMENT",
            area=100,
            address="آدرس",
        )
        value = PropertyAttributeValue(property=prop, attribute=self.attribute)
        value.set_value(created["value"])
        value.save()

        response = self.client.delete(
            f"/basics/api/attributes/{self.attribute.pk}/options/{created['id']}/"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("غیرفعال", response.json()["detail"])

    def test_deleting_an_unknown_option_returns_404(self):
        response = self.client.delete(
            f"/basics/api/attributes/{self.attribute.pk}/options/999999/"
        )
        self.assertEqual(response.status_code, 404)

    def test_a_consultant_cannot_change_options(self):
        option_id = self._add("سنگ").json()["id"]
        self.client.force_login(self.agent)

        self.assertEqual(self._add("آجر").status_code, 403)
        self.assertEqual(
            self.client.delete(
                f"/basics/api/attributes/{self.attribute.pk}/options/{option_id}/"
            ).status_code,
            403,
        )


class BindingPanelTests(TestCase):
    """What the "اتصال به انواع" tab does."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="bind-admin", password="pw", role="ADMIN"
        )
        cls.apartment = PropertyType.objects.get(name="apartment")
        cls.sale = DealType.objects.get(name="sale")
        cls.attribute = Attribute.objects.create(
            name="facade2",
            display_name="نما",
            data_type=Attribute.DataType.TEXT,
            entity=Attribute.Entity.PROPERTY,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_binding_then_reading_it_back(self):
        response = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": self.attribute.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])

        listed = self.client.get(
            f"/basics/api/property-type-attributes/?propertyType={self.apartment.pk}"
        ).json()
        self.assertIn(self.attribute.pk, [row["attribute"] for row in listed])

    def test_a_new_binding_reaches_the_property_form(self):
        """The whole point of the screen: configure once, form follows."""
        self.client.post(
            "/basics/api/property-type-attributes/",
            {
                "propertyType": self.apartment.pk,
                "attribute": self.attribute.pk,
                "isRequired": True,
            },
            content_type="application/json",
        )
        schema = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()

        field = next((f for f in schema["fields"] if f["name"] == "facade2"), None)
        self.assertIsNotNone(field)
        self.assertTrue(field["isRequired"])

    def test_marking_a_binding_required(self):
        created = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": self.attribute.pk},
            content_type="application/json",
        ).json()

        response = self.client.patch(
            f"/basics/api/property-type-attributes/{created['id']}/",
            {"isRequired": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PropertyTypeAttribute.objects.get(pk=created["id"]).is_required
        )

    def test_deactivating_a_binding_hides_it_from_the_form(self):
        created = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": self.attribute.pk},
            content_type="application/json",
        ).json()
        self.client.patch(
            f"/basics/api/property-type-attributes/{created['id']}/",
            {"isActive": False},
            content_type="application/json",
        )

        schema = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        self.assertNotIn("facade2", [f["name"] for f in schema["fields"]])

    def test_unbinding_removes_it_from_the_form(self):
        created = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": self.attribute.pk},
            content_type="application/json",
        ).json()
        self.client.delete(f"/basics/api/property-type-attributes/{created['id']}/")

        schema = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        self.assertNotIn("facade2", [f["name"] for f in schema["fields"]])

    def test_a_property_attribute_cannot_bind_to_a_deal_type(self):
        response = self.client.post(
            "/basics/api/deal-type-attributes/",
            {"dealType": self.sale.pk, "attribute": self.attribute.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_reordering_two_bindings(self):
        second = Attribute.objects.create(
            name="facade3",
            display_name="نمای دوم",
            data_type=Attribute.DataType.TEXT,
            entity=Attribute.Entity.PROPERTY,
        )
        a = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": self.attribute.pk, "sortOrder": 10},
            content_type="application/json",
        ).json()
        b = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": second.pk, "sortOrder": 20},
            content_type="application/json",
        ).json()

        response = self.client.post(
            "/basics/api/property-type-attributes/reorder/",
            [{"id": a["id"], "sortOrder": 20}, {"id": b["id"], "sortOrder": 10}],
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            float(PropertyTypeAttribute.objects.get(pk=a["id"]).sort_order), 20.0
        )

    def test_binding_a_searchable_attribute_reaches_the_list_filters(self):
        searchable = Attribute.objects.create(
            name="custom_view",
            display_name="چشم‌انداز سفارشی",
            data_type=Attribute.DataType.TEXT,
            entity=Attribute.Entity.PROPERTY,
            filter_type=Attribute.FilterType.EXACT,
        )
        response = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": searchable.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertTrue(
            PropertyTypeSearchAttribute.objects.filter(
                property_type=self.apartment, attribute=searchable, is_active=True
            ).exists()
        )
        schema = self.client.get(
            f"/basics/api/schema/search/?propertyType={self.apartment.pk}"
        ).json()
        self.assertIn("custom_view", [row["name"] for row in schema["propertyFilters"]])

    def test_unbinding_drops_the_search_filter(self):
        searchable = Attribute.objects.create(
            name="custom_view_2",
            display_name="چشم‌انداز دوم",
            data_type=Attribute.DataType.TEXT,
            entity=Attribute.Entity.PROPERTY,
            filter_type=Attribute.FilterType.EXACT,
        )
        created = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": searchable.pk},
            content_type="application/json",
        ).json()
        self.client.delete(f"/basics/api/property-type-attributes/{created['id']}/")
        self.assertFalse(
            PropertyTypeSearchAttribute.objects.filter(
                property_type=self.apartment, attribute=searchable
            ).exists()
        )
        schema = self.client.get(
            f"/basics/api/schema/search/?propertyType={self.apartment.pk}"
        ).json()
        self.assertNotIn(
            "custom_view_2", [row["name"] for row in schema["propertyFilters"]]
        )

    def test_deactivating_a_binding_hides_it_from_search(self):
        searchable = Attribute.objects.create(
            name="custom_view_3",
            display_name="چشم‌انداز سوم",
            data_type=Attribute.DataType.TEXT,
            entity=Attribute.Entity.PROPERTY,
            filter_type=Attribute.FilterType.EXACT,
        )
        created = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": searchable.pk},
            content_type="application/json",
        ).json()
        self.client.patch(
            f"/basics/api/property-type-attributes/{created['id']}/",
            {"isActive": False},
            content_type="application/json",
        )
        link = PropertyTypeSearchAttribute.objects.get(
            property_type=self.apartment, attribute=searchable
        )
        self.assertFalse(link.is_active)
        schema = self.client.get(
            f"/basics/api/schema/search/?propertyType={self.apartment.pk}"
        ).json()
        self.assertNotIn(
            "custom_view_3", [row["name"] for row in schema["propertyFilters"]]
        )

    def test_a_none_filter_is_not_added_to_search(self):
        notes = Attribute.objects.create(
            name="internal_notes",
            display_name="یادداشت داخلی اتصال",
            data_type=Attribute.DataType.TEXT,
            entity=Attribute.Entity.PROPERTY,
            filter_type=Attribute.FilterType.NONE,
        )
        response = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.apartment.pk, "attribute": notes.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertFalse(
            PropertyTypeSearchAttribute.objects.filter(
                property_type=self.apartment, attribute=notes
            ).exists()
        )

    def test_binding_a_listing_attribute_reaches_deal_search(self):
        listing_attr = Attribute.objects.create(
            name="listing_note",
            display_name="یادداشت آگهی",
            data_type=Attribute.DataType.TEXT,
            entity=Attribute.Entity.LISTING,
            filter_type=Attribute.FilterType.EXACT,
        )
        response = self.client.post(
            "/basics/api/deal-type-attributes/",
            {"dealType": self.sale.pk, "attribute": listing_attr.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertTrue(
            DealTypeSearchAttribute.objects.filter(
                deal_type=self.sale, attribute=listing_attr, is_active=True
            ).exists()
        )
        schema = self.client.get(
            f"/basics/api/schema/search/?dealType={self.sale.pk}"
        ).json()
        self.assertIn("listing_note", [row["name"] for row in schema["dealFilters"]])


class AttributeListingTests(TestCase):
    """Filters the panel relies on."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="list-admin", password="pw", role="ADMIN"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_all_shows_deactivated_attributes_too(self):
        """The panel needs them so an operator can switch one back on."""
        attribute = Attribute.objects.filter(is_core=False).first()
        attribute.is_active = False
        attribute.save()

        default = self.client.get("/basics/api/attributes/").json()
        everything = self.client.get("/basics/api/attributes/?all=1").json()

        self.assertNotIn(attribute.pk, [a["id"] for a in default])
        self.assertIn(attribute.pk, [a["id"] for a in everything])

    def test_the_entity_filter_splits_property_from_listing(self):
        rows = self.client.get("/basics/api/attributes/?entity=property").json()
        self.assertTrue(all(a["entity"] == "property" for a in rows))

    def test_usage_count_reports_how_many_types_use_it(self):
        rows = self.client.get("/basics/api/attributes/?all=1").json()
        rooms = next(a for a in rows if a["name"] == "rooms")
        self.assertGreater(rooms["usageCount"], 0)

    def test_core_attributes_are_flagged_so_the_ui_can_protect_them(self):
        rows = self.client.get("/basics/api/attributes/?all=1").json()
        area = next(a for a in rows if a["name"] == "area")
        self.assertTrue(area["isCore"])
