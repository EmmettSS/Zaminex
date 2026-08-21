"""Tests for the EAV value engine (typed storage, coercion, validation)."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.basics.models import Attribute, AttributeOption, PropertyType, PropertyUsage
from apps.properties.models import Property, PropertyAttributeValue

User = get_user_model()


class AttributeValueStorageTests(TestCase):
    """Each data type must land in — and read back from — the right column."""

    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(
            username="agent", password="x", role="AGENT"
        )
        usage = PropertyUsage.objects.create(name="residential", display_name="مسکونی")
        cls.apartment = PropertyType.objects.create(
            name="apartment", display_name="آپارتمان", property_usage=usage
        )
        cls.property = Property.objects.create(
            title="ملک نمونه",
            internal_code="EAV-1",
            consultant=cls.agent,
            property_type="APARTMENT",
            property_type_ref=cls.apartment,
            property_usage=usage,
            deal_type="SALE",
            price=1_000_000,
            area=100,
            address="آدرس",
            neighborhood="محله",
        )

    def _store(self, attribute, raw):
        value = PropertyAttributeValue(property=self.property, attribute=attribute)
        value.set_value(raw)
        value.save()
        return value

    def test_integer_is_stored_in_the_integer_column(self):
        attribute = Attribute.objects.create(
            name="total_floors", display_name="طبقات", data_type=Attribute.DataType.INTEGER
        )
        value = self._store(attribute, "12")

        self.assertEqual(value.value_integer, 12)
        self.assertIsNone(value.value_text, "other columns stay empty")
        self.assertEqual(value.value, 12)

    def test_decimal_is_stored_in_the_decimal_column(self):
        attribute = Attribute.objects.create(
            name="land_area", display_name="متراژ زمین", data_type=Attribute.DataType.DECIMAL
        )
        value = self._store(attribute, "450.75")
        self.assertEqual(value.value_decimal, Decimal("450.75"))

    def test_boolean_accepts_the_usual_representations(self):
        attribute = Attribute.objects.create(
            name="parking", display_name="پارکینگ", data_type=Attribute.DataType.BOOLEAN
        )
        for raw, expected in [
            (True, True), ("true", True), ("1", True), ("بله", True),
            (False, False), ("false", False), ("0", False), ("خیر", False),
        ]:
            with self.subTest(raw=raw):
                value = PropertyAttributeValue(
                    property=self.property, attribute=attribute
                )
                value.set_value(raw)
                self.assertIs(value.value_boolean, expected)

    def test_date_accepts_iso_strings_and_date_objects(self):
        attribute = Attribute.objects.create(
            name="handover", display_name="تحویل", data_type=Attribute.DataType.DATE
        )
        self.assertEqual(
            self._store(attribute, "2026-03-21").value_date, datetime.date(2026, 3, 21)
        )

    def test_multiselect_is_stored_as_json(self):
        attribute = Attribute.objects.create(
            name="views", display_name="نما", data_type=Attribute.DataType.MULTISELECT
        )
        for value, label in [("sea", "دریا"), ("mountain", "کوه")]:
            AttributeOption.objects.create(
                attribute=attribute, value=value, display_name=label
            )

        stored = self._store(attribute, ["sea", "mountain"])
        self.assertEqual(stored.value_json, ["sea", "mountain"])
        self.assertEqual(stored.display_value, "دریا، کوه")

    def test_thousands_separators_are_accepted(self):
        """Persian price inputs arrive formatted; the value must still parse."""
        attribute = Attribute.objects.create(
            name="fee", display_name="هزینه", data_type=Attribute.DataType.INTEGER
        )
        self.assertEqual(self._store(attribute, "1,500,000").value_integer, 1_500_000)

    def test_changing_the_value_clears_the_previous_column(self):
        """Switching types must not leave a stale value behind."""
        attribute = Attribute.objects.create(
            name="note", display_name="یادداشت", data_type=Attribute.DataType.TEXT
        )
        value = self._store(attribute, "متن")
        self.assertEqual(value.value_text, "متن")

        attribute.data_type = Attribute.DataType.INTEGER
        attribute.save()
        value.attribute.refresh_from_db()
        value.set_value("5")

        self.assertEqual(value.value_integer, 5)
        self.assertIsNone(value.value_text, "the old text value must be cleared")


class AttributeValueValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(username="agent2", password="x", role="AGENT")
        usage = PropertyUsage.objects.create(name="residential", display_name="مسکونی")
        cls.property = Property.objects.create(
            title="ملک",
            internal_code="EAV-2",
            consultant=cls.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            price=1,
            area=1,
            address="آ",
            neighborhood="م",
        )

    def _value(self, attribute):
        return PropertyAttributeValue(property=self.property, attribute=attribute)

    def test_non_numeric_input_is_rejected_with_a_persian_message(self):
        attribute = Attribute.objects.create(
            name="floors", display_name="طبقات", data_type=Attribute.DataType.INTEGER
        )
        with self.assertRaises(ValidationError) as ctx:
            self._value(attribute).set_value("abc")
        self.assertIn("طبقات", str(ctx.exception))

    def test_a_value_outside_the_option_list_is_rejected(self):
        attribute = Attribute.objects.create(
            name="doc", display_name="سند", data_type=Attribute.DataType.SELECT
        )
        AttributeOption.objects.create(
            attribute=attribute, value="single", display_name="تک برگ"
        )
        with self.assertRaises(ValidationError):
            self._value(attribute).set_value("nonexistent")

    def test_inactive_options_are_not_accepted(self):
        attribute = Attribute.objects.create(
            name="doc2", display_name="سند", data_type=Attribute.DataType.SELECT
        )
        AttributeOption.objects.create(
            attribute=attribute, value="old", display_name="قدیمی", is_active=False
        )
        with self.assertRaises(ValidationError):
            self._value(attribute).set_value("old")

    def test_core_attributes_cannot_be_stored_in_the_eav_table(self):
        """Core values belong in their real column, not here."""
        attribute = Attribute.objects.create(
            name="area",
            display_name="متراژ",
            data_type=Attribute.DataType.DECIMAL,
            is_core=True,
            core_field="area",
        )
        value = self._value(attribute)
        value.value_decimal = Decimal("120")
        with self.assertRaises(ValidationError):
            value.full_clean()

    def test_an_empty_value_clears_every_column(self):
        attribute = Attribute.objects.create(
            name="opt", display_name="اختیاری", data_type=Attribute.DataType.INTEGER
        )
        value = self._value(attribute)
        value.set_value("5")
        value.set_value("")
        self.assertIsNone(value.value_integer)

    def test_the_same_attribute_cannot_be_recorded_twice_for_one_property(self):
        from django.db import IntegrityError

        attribute = Attribute.objects.create(
            name="dup", display_name="تکراری", data_type=Attribute.DataType.TEXT
        )
        PropertyAttributeValue.objects.create(
            property=self.property, attribute=attribute, value_text="a"
        )
        with self.assertRaises(IntegrityError):
            PropertyAttributeValue.objects.create(
                property=self.property, attribute=attribute, value_text="b"
            )


class AttributeValueQueryTests(TestCase):
    """Filtering must use the typed column so comparisons are numeric."""

    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(username="agent3", password="x", role="AGENT")
        cls.attribute = Attribute.objects.create(
            name="total_floors", display_name="طبقات", data_type=Attribute.DataType.INTEGER
        )
        for index, floors in enumerate([5, 12, 25], start=1):
            prop = Property.objects.create(
                title=f"ملک {index}",
                internal_code=f"Q-{index}",
                consultant=cls.agent,
                property_type="APARTMENT",
                deal_type="SALE",
                price=1,
                area=1,
                address="آ",
                neighborhood="م",
            )
            value = PropertyAttributeValue(property=prop, attribute=cls.attribute)
            value.set_value(floors)
            value.save()

    def test_numeric_range_filtering(self):
        matches = Property.objects.filter(
            attribute_values__attribute=self.attribute,
            attribute_values__value_integer__gte=10,
        )
        self.assertEqual(matches.count(), 2, "12 and 25 are >= 10, 5 is not")

    def test_comparison_is_numeric_not_lexicographic(self):
        """A string comparison would rank "5" above "25"."""
        matches = Property.objects.filter(
            attribute_values__attribute=self.attribute,
            attribute_values__value_integer__gt=20,
        )
        self.assertEqual(matches.count(), 1)
