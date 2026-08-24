"""API tests: permissions, form schemas and the management endpoints."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.basics.models import (
    Attribute,
    AttributeOption,
    DealType,
    DealTypeAttribute,
    PropertyType,
    PropertyTypeAttribute,
    PropertyTypeSearchAttribute,
    PropertyUsage,
)

User = get_user_model()


class BasicsAPITestCase(TestCase):
    """Shared fixture: one usage, two types, a deal type and some attributes."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin-user", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="agent-user", password="pw", role="AGENT"
        )

        cls.usage = PropertyUsage.objects.create(
            name="residential", display_name="مسکونی"
        )
        cls.apartment = PropertyType.objects.create(
            name="apartment", display_name="آپارتمان", property_usage=cls.usage
        )
        cls.land = PropertyType.objects.create(
            name="land", display_name="زمین", property_usage=cls.usage
        )
        cls.sale = DealType.objects.create(name="sale", display_name="فروش")

        cls.area = Attribute.objects.create(
            name="area",
            display_name="متراژ",
            data_type=Attribute.DataType.DECIMAL,
            filter_type=Attribute.FilterType.RANGE_FAST,
            is_core=True,
            core_field="area",
            sort_order=10,
        )
        cls.rooms = Attribute.objects.create(
            name="rooms",
            display_name="تعداد اتاق",
            data_type=Attribute.DataType.INTEGER,
            is_core=True,
            core_field="rooms",
            sort_order=20,
        )
        cls.parking = Attribute.objects.create(
            name="parking",
            display_name="پارکینگ",
            data_type=Attribute.DataType.BOOLEAN,
            is_facility=True,
            sort_order=30,
        )
        cls.doc = Attribute.objects.create(
            name="document_type",
            display_name="نوع سند",
            data_type=Attribute.DataType.SELECT,
            sort_order=40,
        )
        AttributeOption.objects.create(
            attribute=cls.doc, value="single", display_name="تک برگ"
        )
        AttributeOption.objects.create(
            attribute=cls.doc, value="retired", display_name="منسوخ", is_active=False
        )
        cls.deposit = Attribute.objects.create(
            name="deposit",
            display_name="مبلغ رهن",
            data_type=Attribute.DataType.DECIMAL,
            entity=Attribute.Entity.LISTING,
            input_type=Attribute.InputType.PRICE,
        )

        # Apartment gets everything; land deliberately has no `rooms`.
        for attribute, order in [(cls.area, 10), (cls.rooms, 20), (cls.parking, 30), (cls.doc, 40)]:
            PropertyTypeAttribute.objects.create(
                property_type=cls.apartment,
                attribute=attribute,
                sort_order=order,
                is_required=(attribute == cls.area),
            )
        PropertyTypeAttribute.objects.create(
            property_type=cls.land, attribute=cls.area, sort_order=10, is_required=True
        )
        PropertyTypeAttribute.objects.create(
            property_type=cls.land, attribute=cls.doc, sort_order=20
        )

        PropertyTypeSearchAttribute.objects.create(
            property_type=cls.apartment, attribute=cls.area, sort_order=10
        )
        PropertyTypeSearchAttribute.objects.create(
            property_type=cls.apartment, attribute=cls.parking, sort_order=20
        )

        DealTypeAttribute.objects.create(deal_type=cls.sale, attribute=cls.deposit)


class PermissionTests(BasicsAPITestCase):
    def test_anonymous_users_are_refused(self):
        response = self.client.get("/basics/api/catalog/")
        self.assertIn(response.status_code, (401, 403))

    def test_a_consultant_can_read_the_catalogue(self):
        self.client.force_login(self.agent)
        response = self.client.get("/basics/api/property-types/")
        self.assertEqual(response.status_code, 200)

    def test_a_consultant_cannot_create_reference_data(self):
        self.client.force_login(self.agent)
        response = self.client.post(
            "/basics/api/property-types/",
            {"name": "x", "displayName": "ایکس", "propertyUsage": self.usage.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_a_consultant_cannot_delete_reference_data(self):
        self.client.force_login(self.agent)
        response = self.client.delete(f"/basics/api/property-types/{self.apartment.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_an_admin_can_create_reference_data(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/basics/api/property-types/",
            {"name": "duplex", "displayName": "دوبلکس", "propertyUsage": self.usage.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)


class PropertyFormSchemaTests(BasicsAPITestCase):
    def setUp(self):
        self.client.force_login(self.agent)

    def test_apartment_exposes_rooms_and_land_does_not(self):
        """The client's example, enforced end to end."""
        apartment = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        land = self.client.get(
            "/basics/api/schema/property-form/?propertyType=land"
        ).json()

        apartment_fields = {f["name"] for f in apartment["fields"]}
        land_fields = {f["name"] for f in land["fields"]}

        self.assertIn("rooms", apartment_fields)
        self.assertNotIn("rooms", land_fields)
        self.assertIn("area", apartment_fields, "shared attributes still apply")
        self.assertIn("area", land_fields)

    def test_facilities_are_returned_separately(self):
        payload = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()

        facility_names = {f["name"] for f in payload["facilities"]}
        field_names = {f["name"] for f in payload["fields"]}

        self.assertIn("parking", facility_names)
        self.assertNotIn(
            "parking", field_names, "a facility must not also appear as a normal field"
        )

    def test_fields_arrive_in_the_configured_order(self):
        payload = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        orders = [float(f["sortOrder"]) for f in payload["fields"]]
        self.assertEqual(orders, sorted(orders))

    def test_core_fields_are_flagged_with_their_column(self):
        payload = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        area = next(f for f in payload["fields"] if f["name"] == "area")

        self.assertTrue(area["isCore"])
        self.assertEqual(area["coreField"], "area")
        self.assertTrue(area["isRequired"])

    def test_select_fields_carry_only_active_options(self):
        payload = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        doc = next(f for f in payload["fields"] if f["name"] == "document_type")

        values = {o["value"] for o in doc["options"]}
        self.assertEqual(values, {"single"}, "the inactive option must be hidden")

    def test_a_deactivated_binding_disappears_from_the_form(self):
        PropertyTypeAttribute.objects.filter(
            property_type=self.apartment, attribute=self.doc
        ).update(is_active=False)

        payload = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        self.assertNotIn(
            "document_type", {f["name"] for f in payload["fields"]}
        )

    def test_a_deactivated_attribute_disappears_everywhere(self):
        self.doc.is_active = False
        self.doc.save()

        payload = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        self.assertNotIn("document_type", {f["name"] for f in payload["fields"]})

    def test_the_type_can_be_addressed_by_id_or_by_name(self):
        by_name = self.client.get(
            "/basics/api/schema/property-form/?propertyType=apartment"
        ).json()
        by_id = self.client.get(
            f"/basics/api/schema/property-form/?propertyType={self.apartment.pk}"
        ).json()
        self.assertEqual(by_name["fields"], by_id["fields"])

    def test_a_missing_parameter_returns_400(self):
        self.assertEqual(
            self.client.get("/basics/api/schema/property-form/").status_code, 400
        )

    def test_an_unknown_type_returns_404(self):
        self.assertEqual(
            self.client.get(
                "/basics/api/schema/property-form/?propertyType=nope"
            ).status_code,
            404,
        )


class ListingFormSchemaTests(BasicsAPITestCase):
    def setUp(self):
        self.client.force_login(self.agent)

    def test_the_deal_type_drives_the_listing_form(self):
        payload = self.client.get(
            "/basics/api/schema/listing-form/?dealType=sale"
        ).json()

        self.assertEqual(payload["dealType"]["displayName"], "فروش")
        self.assertIn("deposit", {f["name"] for f in payload["fields"]})

    def test_price_inputs_are_marked_for_the_form_renderer(self):
        payload = self.client.get(
            "/basics/api/schema/listing-form/?dealType=sale"
        ).json()
        deposit = next(f for f in payload["fields"] if f["name"] == "deposit")
        self.assertEqual(deposit["inputType"], "price")


class SearchSchemaTests(BasicsAPITestCase):
    def setUp(self):
        self.client.force_login(self.agent)

    def test_search_filters_are_scoped_to_the_property_type(self):
        payload = self.client.get(
            "/basics/api/schema/search/?propertyType=apartment"
        ).json()
        names = {f["name"] for f in payload["propertyFilters"]}
        self.assertEqual(names, {"area", "parking"})

    def test_filters_expose_the_strategy_and_storage(self):
        payload = self.client.get(
            "/basics/api/schema/search/?propertyType=apartment"
        ).json()
        area = next(f for f in payload["propertyFilters"] if f["name"] == "area")

        self.assertEqual(area["filterType"], "range_fast")
        self.assertTrue(area["isCore"])


class CatalogTests(BasicsAPITestCase):
    def setUp(self):
        self.client.force_login(self.agent)

    def test_the_catalogue_returns_everything_in_one_call(self):
        payload = self.client.get("/basics/api/catalog/").json()

        self.assertEqual(len(payload["usages"]), 1)
        self.assertEqual(len(payload["propertyTypes"]), 2)
        self.assertEqual(len(payload["dealTypes"]), 1)

    def test_inactive_rows_are_hidden(self):
        self.land.is_active = False
        self.land.save()

        payload = self.client.get("/basics/api/catalog/").json()
        self.assertEqual({t["name"] for t in payload["propertyTypes"]}, {"apartment"})


class AttributeManagementTests(BasicsAPITestCase):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_creating_an_attribute(self):
        response = self.client.post(
            "/basics/api/attributes/",
            {
                "name": "has_view",
                "displayName": "چشم‌انداز",
                "dataType": "boolean",
                "entity": "property",
                "isFacility": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Attribute.objects.filter(name="has_view").exists())

    def test_the_system_key_must_be_unique(self):
        response = self.client.post(
            "/basics/api/attributes/",
            {"name": "parking", "displayName": "تکراری", "dataType": "text"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_the_system_key_cannot_be_changed_after_creation(self):
        """Stored rows reference it, so renaming would orphan them."""
        response = self.client.patch(
            f"/basics/api/attributes/{self.parking.pk}/",
            {"name": "renamed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_the_display_name_can_be_changed(self):
        response = self.client.patch(
            f"/basics/api/attributes/{self.parking.pk}/",
            {"displayName": "جای پارک"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.parking.refresh_from_db()
        self.assertEqual(self.parking.display_name, "جای پارک")

    def test_a_core_attribute_cannot_be_deleted(self):
        response = self.client.delete(f"/basics/api/attributes/{self.area.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Attribute.objects.filter(pk=self.area.pk).exists())

    def test_the_data_type_cannot_change_once_values_exist(self):
        from apps.properties.models import Property, PropertyAttributeValue

        prop = Property.objects.create(
            title="ملک",
            internal_code="CHG-1",
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            price=1,
            area=1,
            address="آ",
            neighborhood="م",
        )
        value = PropertyAttributeValue(property=prop, attribute=self.doc)
        value.set_value("single")
        value.save()

        response = self.client.patch(
            f"/basics/api/attributes/{self.doc.pk}/",
            {"dataType": "integer"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_deleting_an_attribute_is_a_soft_delete(self):
        response = self.client.delete(f"/basics/api/attributes/{self.doc.pk}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Attribute.objects.filter(pk=self.doc.pk).exists())
        self.assertTrue(Attribute.all_objects.filter(pk=self.doc.pk).exists())

    def test_a_soft_deleted_attribute_can_be_restored(self):
        self.client.delete(f"/basics/api/attributes/{self.doc.pk}/")
        response = self.client.post(f"/basics/api/attributes/{self.doc.pk}/restore/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Attribute.objects.filter(pk=self.doc.pk).exists())

    def test_attributes_can_be_filtered_by_entity(self):
        payload = self.client.get("/basics/api/attributes/?entity=listing").json()
        self.assertEqual({a["name"] for a in payload}, {"deposit"})


class BindingManagementTests(BasicsAPITestCase):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_binding_an_attribute_to_a_property_type(self):
        duplex = PropertyType.objects.create(
            name="duplex", display_name="دوبلکس", property_usage=self.usage
        )
        response = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": duplex.pk, "attribute": self.rooms.pk, "isRequired": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

    def test_a_listing_attribute_cannot_be_bound_to_a_property_type(self):
        response = self.client.post(
            "/basics/api/property-type-attributes/",
            {"propertyType": self.land.pk, "attribute": self.deposit.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_reordering_the_form_fields(self):
        links = list(
            PropertyTypeAttribute.objects.filter(property_type=self.apartment).order_by(
                "sort_order"
            )
        )
        payload = [
            {"id": link.pk, "sortOrder": (len(links) - index) * 10}
            for index, link in enumerate(links)
        ]

        response = self.client.post(
            "/basics/api/property-type-attributes/reorder/",
            payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        reordered = list(
            PropertyTypeAttribute.objects.filter(property_type=self.apartment)
            .order_by("sort_order")
            .values_list("attribute__name", flat=True)
        )
        self.assertEqual(reordered[0], links[-1].attribute.name)

    def test_a_consultant_cannot_reorder(self):
        self.client.force_login(self.agent)
        response = self.client.post(
            "/basics/api/property-type-attributes/reorder/",
            [],
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


class UsageProtectionTests(BasicsAPITestCase):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_a_usage_with_active_types_cannot_be_deleted(self):
        response = self.client.delete(f"/basics/api/property-usages/{self.usage.pk}/")
        self.assertEqual(response.status_code, 400)

    def test_an_empty_usage_can_be_deleted(self):
        empty = PropertyUsage.objects.create(name="industrial", display_name="صنعتی")
        response = self.client.delete(f"/basics/api/property-usages/{empty.pk}/")
        self.assertEqual(response.status_code, 204)

    def test_types_can_be_filtered_by_usage(self):
        payload = self.client.get(
            "/basics/api/property-types/?usage=residential"
        ).json()
        self.assertEqual(len(payload), 2)
