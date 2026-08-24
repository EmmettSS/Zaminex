"""Model-level tests for the reference data and the attribute engine."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.basics.models import (
    Attribute,
    AttributeOption,
    DealType,
    PropertyType,
    PropertyTypeAttribute,
    PropertyUsage,
)


class SoftDeleteTests(TestCase):
    def setUp(self):
        self.usage = PropertyUsage.objects.create(
            name="residential", display_name="مسکونی"
        )

    def test_delete_hides_the_row_but_keeps_it(self):
        self.usage.delete()

        self.assertEqual(PropertyUsage.objects.count(), 0, "default manager hides it")
        self.assertEqual(PropertyUsage.all_objects.count(), 1, "row still exists")

        restored = PropertyUsage.all_objects.get(pk=self.usage.pk)
        self.assertIsNotNone(restored.deleted_at)
        self.assertFalse(
            restored.is_active,
            "a deleted row must also be inactive so it cannot resurface",
        )

    def test_name_can_be_reused_after_soft_delete(self):
        """The unique index only covers live rows.

        A plain `unique=True` would make this fail against a row the user can
        no longer see.
        """
        self.usage.delete()
        recreated = PropertyUsage.objects.create(
            name="residential", display_name="مسکونی (جدید)"
        )
        self.assertNotEqual(recreated.pk, self.usage.pk)

    def test_duplicate_name_among_live_rows_is_rejected(self):
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            PropertyUsage.objects.create(name="residential", display_name="تکراری")

    def test_restore_brings_the_row_back(self):
        self.usage.delete()
        PropertyUsage.all_objects.get(pk=self.usage.pk).restore()
        self.assertEqual(PropertyUsage.objects.count(), 1)

    def test_hard_delete_removes_the_row(self):
        self.usage.delete(hard=True)
        self.assertEqual(PropertyUsage.all_objects.count(), 0)

    def test_queryset_delete_is_also_soft(self):
        PropertyUsage.objects.all().delete()
        self.assertEqual(PropertyUsage.objects.count(), 0)
        self.assertEqual(PropertyUsage.all_objects.count(), 1)


class AttributeValidationTests(TestCase):
    def test_core_attribute_requires_a_column_name(self):
        attribute = Attribute(
            name="area",
            display_name="متراژ",
            data_type=Attribute.DataType.DECIMAL,
            is_core=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            attribute.full_clean()
        self.assertIn("core_field", ctx.exception.message_dict)

    def test_column_name_is_rejected_on_a_non_core_attribute(self):
        attribute = Attribute(
            name="parking",
            display_name="پارکینگ",
            data_type=Attribute.DataType.BOOLEAN,
            is_core=False,
            core_field="parking",
        )
        with self.assertRaises(ValidationError) as ctx:
            attribute.full_clean()
        self.assertIn("core_field", ctx.exception.message_dict)

    def test_value_field_maps_each_data_type_to_its_column(self):
        cases = {
            Attribute.DataType.TEXT: "value_text",
            Attribute.DataType.INTEGER: "value_integer",
            Attribute.DataType.DECIMAL: "value_decimal",
            Attribute.DataType.BOOLEAN: "value_boolean",
            Attribute.DataType.DATE: "value_date",
            Attribute.DataType.SELECT: "value_text",
            Attribute.DataType.MULTISELECT: "value_json",
        }
        for data_type, expected in cases.items():
            with self.subTest(data_type=data_type):
                attribute = Attribute(
                    name=f"a_{data_type}", display_name="x", data_type=data_type
                )
                self.assertEqual(attribute.value_field, expected)


class AttributeBindingTests(TestCase):
    def setUp(self):
        self.usage = PropertyUsage.objects.create(
            name="residential", display_name="مسکونی"
        )
        self.apartment = PropertyType.objects.create(
            name="apartment", display_name="آپارتمان", property_usage=self.usage
        )
        self.land = PropertyType.objects.create(
            name="land", display_name="زمین", property_usage=self.usage
        )
        self.rooms = Attribute.objects.create(
            name="rooms",
            display_name="تعداد اتاق",
            data_type=Attribute.DataType.INTEGER,
            entity=Attribute.Entity.PROPERTY,
        )
        self.deposit = Attribute.objects.create(
            name="deposit",
            display_name="مبلغ رهن",
            data_type=Attribute.DataType.DECIMAL,
            entity=Attribute.Entity.LISTING,
        )

    def test_rooms_applies_to_apartment_but_not_to_land(self):
        """The client's own example of type-scoped attributes."""
        PropertyTypeAttribute.objects.create(
            property_type=self.apartment, attribute=self.rooms, is_required=True
        )

        apartment_attrs = [
            link.attribute.name for link in self.apartment.attribute_links.all()
        ]
        land_attrs = [link.attribute.name for link in self.land.attribute_links.all()]

        self.assertIn("rooms", apartment_attrs)
        self.assertNotIn("rooms", land_attrs)

    def test_a_listing_attribute_cannot_be_bound_to_a_property_type(self):
        link = PropertyTypeAttribute(
            property_type=self.apartment, attribute=self.deposit
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_the_same_attribute_cannot_be_bound_twice(self):
        from django.db import IntegrityError

        PropertyTypeAttribute.objects.create(
            property_type=self.apartment, attribute=self.rooms
        )
        with self.assertRaises(IntegrityError):
            PropertyTypeAttribute.objects.create(
                property_type=self.apartment, attribute=self.rooms
            )


class AttributeOptionTests(TestCase):
    def setUp(self):
        self.attribute = Attribute.objects.create(
            name="document_type",
            display_name="نوع سند",
            data_type=Attribute.DataType.SELECT,
        )

    def test_option_values_are_unique_per_attribute(self):
        from django.db import IntegrityError

        AttributeOption.objects.create(
            attribute=self.attribute, value="single_deed", display_name="تک برگ"
        )
        with self.assertRaises(IntegrityError):
            AttributeOption.objects.create(
                attribute=self.attribute, value="single_deed", display_name="تکراری"
            )

    def test_options_are_ordered_by_sort_order(self):
        AttributeOption.objects.create(
            attribute=self.attribute, value="b", display_name="ب", sort_order=Decimal(20)
        )
        AttributeOption.objects.create(
            attribute=self.attribute, value="a", display_name="الف", sort_order=Decimal(10)
        )
        self.assertEqual(
            list(self.attribute.options.values_list("value", flat=True)), ["a", "b"]
        )
