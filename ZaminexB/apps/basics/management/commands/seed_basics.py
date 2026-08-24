"""Populate the reference-data tables with the Zaminex starter set.

Creates the three usages (مسکونی / تجاری / اداری), the property types that
belong to each, the deal types, and a library of attributes wired to the types
that actually use them — so "تعداد اتاق" reaches آپارتمان but not زمین.

The command is idempotent: it matches on the immutable ``name`` key and updates
in place, so re-running it after adding a new type is safe and never duplicates
rows. Labels an administrator edited by hand are preserved (see ``--force``).

    python manage.py seed_basics            # create/extend, keep local edits
    python manage.py seed_basics --force    # also reset display names to default
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.basics.models import (
    Attribute,
    AttributeOption,
    DealType,
    DealTypeAttribute,
    DealTypeSearchAttribute,
    PropertyType,
    PropertyTypeAttribute,
    PropertyTypeSearchAttribute,
    PropertyUsage,
)

A = Attribute.DataType
F = Attribute.FilterType
E = Attribute.Entity

# --- usages ----------------------------------------------------------------
USAGES = [
    ("residential", "مسکونی", 10),
    ("commercial", "تجاری", 20),
    ("office", "اداری", 30),
]

# --- property types: (name, label, usage, sort) ----------------------------
# The first five mirror the legacy Property.PropertyType choices so existing
# rows migrate cleanly; the rest round out the catalogue.
PROPERTY_TYPES = [
    ("apartment", "آپارتمان", "residential", 10),
    ("villa", "ویلا", "residential", 20),
    ("townhouse", "خانه ویلایی", "residential", 30),
    ("studio", "سوئیت", "residential", 40),
    ("penthouse", "پنت‌هاوس", "residential", 50),
    ("land", "زمین", "residential", 60),
    ("shop", "مغازه", "commercial", 10),
    ("commercial", "ملک تجاری", "commercial", 20),
    ("warehouse", "انبار", "commercial", 30),
    ("office", "دفتر کار", "office", 10),
    ("office_building", "ساختمان اداری", "office", 20),
    ("other", "سایر", "residential", 900),
]

# --- deal types ------------------------------------------------------------
DEAL_TYPES = [
    ("sale", "فروش", 10),
    ("mortgage_rent", "رهن و اجاره", 20),
    ("full_mortgage", "رهن کامل", 30),
    ("presale", "پیش‌فروش", 40),
    ("exchange", "معاوضه", 50),
    ("partnership", "مشارکت در ساخت", 60),
]

# --- attributes ------------------------------------------------------------
# (name, label, data_type, filter_type, unit, entity, is_facility, is_core,
#  core_field, sort)
ATTRIBUTES = [
    # Core property columns — stored on Property itself, not in EAV.
    ("area", "متراژ", A.DECIMAL, F.RANGE_FAST, "متر مربع", E.PROPERTY, False, True, "area", 10),
    ("rooms", "تعداد اتاق", A.INTEGER, F.RANGE, "عدد", E.PROPERTY, False, True, "rooms", 20),
    ("floor", "طبقه", A.INTEGER, F.RANGE, "", E.PROPERTY, False, True, "floor", 30),
    ("built_year", "سال ساخت", A.INTEGER, F.RANGE, "", E.PROPERTY, False, True, "built_year", 40),
    # Dynamic property attributes.
    ("total_floors", "تعداد کل طبقات", A.INTEGER, F.RANGE, "", E.PROPERTY, False, False, "", 50),
    ("units_per_floor", "واحد در طبقه", A.INTEGER, F.EXACT, "", E.PROPERTY, False, False, "", 60),
    ("building_direction", "جهت ساختمان", A.SELECT, F.EXACT, "", E.PROPERTY, False, False, "", 70),
    ("document_type", "نوع سند", A.SELECT, F.EXACT, "", E.PROPERTY, False, False, "", 80),
    ("renovation_status", "وضعیت بازسازی", A.SELECT, F.EXACT, "", E.PROPERTY, False, False, "", 90),
    ("land_area", "متراژ زمین", A.DECIMAL, F.RANGE, "متر مربع", E.PROPERTY, False, False, "", 100),
    ("building_area", "متراژ بنا", A.DECIMAL, F.RANGE, "متر مربع", E.PROPERTY, False, False, "", 110),
    ("frontage", "بر زمین", A.DECIMAL, F.RANGE, "متر", E.PROPERTY, False, False, "", 120),
    ("bathrooms", "تعداد سرویس بهداشتی", A.INTEGER, F.RANGE, "عدد", E.PROPERTY, False, False, "", 130),
    ("shop_width", "دهنه مغازه", A.DECIMAL, F.RANGE, "متر", E.PROPERTY, False, False, "", 140),
    ("has_balcony", "بالکن", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 200),
    # Facilities (boolean, grouped in the UI).
    ("parking", "پارکینگ", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 210),
    ("elevator", "آسانسور", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 220),
    ("storage", "انباری", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 230),
    ("pool", "استخر", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 240),
    ("sauna", "سونا", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 250),
    ("jacuzzi", "جکوزی", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 260),
    ("security_guard", "نگهبانی", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 270),
    ("central_antenna", "آنتن مرکزی", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 280),
    ("remote_door", "درب ریموت", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 290),
    ("water_well", "چاه آب", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 300),
    ("electricity", "برق", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 310),
    ("gas", "گاز", A.BOOLEAN, F.EXISTS, "", E.PROPERTY, True, False, "", 320),
]

# Select-type attributes and their options.
ATTRIBUTE_OPTIONS = {
    "building_direction": [
        ("north", "شمالی", 10),
        ("south", "جنوبی", 20),
        ("east", "شرقی", 30),
        ("west", "غربی", 40),
        ("north_south", "شمالی جنوبی", 50),
    ],
    "document_type": [
        ("single_deed", "تک برگ", 10),
        ("shared_deed", "مشاع", 20),
        ("endowment", "وقفی", 30),
        ("agreement", "قولنامه‌ای", 40),
    ],
    "renovation_status": [
        ("new", "نوساز", 10),
        ("renovated", "بازسازی شده", 20),
        ("needs_renovation", "نیاز به بازسازی", 30),
    ],
}

# Which attributes each property type offers.
# "*" = every type. (attribute, required)
TYPE_ATTRIBUTES: dict[str, list[tuple[str, bool]]] = {
    "*": [("area", True)],
    "apartment": [
        ("rooms", True), ("floor", False), ("built_year", False),
        ("total_floors", False), ("units_per_floor", False),
        ("building_direction", False), ("document_type", False),
        ("renovation_status", False), ("bathrooms", False),
        ("has_balcony", False), ("parking", False), ("elevator", False),
        ("storage", False), ("security_guard", False), ("remote_door", False),
    ],
    "penthouse": [
        ("rooms", True), ("floor", False), ("built_year", False),
        ("total_floors", False), ("building_direction", False),
        ("document_type", False), ("bathrooms", False), ("has_balcony", False),
        ("parking", False), ("elevator", False), ("storage", False),
        ("pool", False), ("jacuzzi", False), ("security_guard", False),
    ],
    "studio": [
        ("rooms", False), ("floor", False), ("built_year", False),
        ("document_type", False), ("bathrooms", False), ("parking", False),
        ("elevator", False),
    ],
    "villa": [
        ("rooms", True), ("built_year", False), ("land_area", False),
        ("building_area", False), ("building_direction", False),
        ("document_type", False), ("renovation_status", False),
        ("bathrooms", False), ("parking", False), ("pool", False),
        ("sauna", False), ("jacuzzi", False), ("storage", False),
    ],
    "townhouse": [
        ("rooms", True), ("built_year", False), ("land_area", False),
        ("building_area", False), ("document_type", False),
        ("bathrooms", False), ("parking", False), ("storage", False),
    ],
    "land": [
        # Deliberately no `rooms` — the client's own example of an attribute
        # that must not appear for land.
        ("land_area", True), ("frontage", False), ("document_type", False),
        ("water_well", False), ("electricity", False), ("gas", False),
    ],
    "shop": [
        ("built_year", False), ("shop_width", False), ("document_type", False),
        ("bathrooms", False), ("parking", False), ("storage", False),
        ("security_guard", False),
    ],
    "commercial": [
        ("floor", False), ("built_year", False), ("document_type", False),
        ("parking", False), ("elevator", False), ("security_guard", False),
    ],
    "warehouse": [
        ("built_year", False), ("land_area", False), ("document_type", False),
        ("electricity", False), ("gas", False),
    ],
    "office": [
        ("rooms", False), ("floor", False), ("built_year", False),
        ("total_floors", False), ("document_type", False),
        ("bathrooms", False), ("parking", False), ("elevator", False),
        ("security_guard", False),
    ],
    "office_building": [
        ("built_year", False), ("total_floors", False),
        ("document_type", False), ("parking", False), ("elevator", False),
        ("security_guard", False),
    ],
    "other": [("document_type", False)],
}

# Filters offered per property type (order matters in the UI).
TYPE_SEARCH_ATTRIBUTES: dict[str, list[str]] = {
    "*": ["area"],
    "apartment": ["rooms", "floor", "built_year", "parking", "elevator", "storage"],
    "penthouse": ["rooms", "built_year", "parking", "elevator", "pool"],
    "studio": ["rooms", "built_year", "parking"],
    "villa": ["rooms", "land_area", "built_year", "pool", "parking"],
    "townhouse": ["rooms", "land_area", "built_year", "parking"],
    "land": ["land_area", "frontage", "document_type"],
    "shop": ["shop_width", "built_year", "parking"],
    "commercial": ["floor", "built_year", "parking"],
    "warehouse": ["land_area", "built_year"],
    "office": ["rooms", "floor", "built_year", "parking", "elevator"],
    "office_building": ["total_floors", "built_year", "parking", "elevator"],
    "other": [],
}


class Command(BaseCommand):
    help = "Seed the reference-data tables (usages, property types, deal types, attributes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite display names and settings that were edited locally.",
        )

    def _upsert(self, model, name, defaults, force):
        """Create the row, or update it while respecting local edits."""
        obj = model.all_objects.filter(name=name).first()
        if obj is None:
            return model.objects.create(name=name, **defaults), True
        if force:
            for field, value in defaults.items():
                setattr(obj, field, value)
            obj.save()
        return obj, False

    @transaction.atomic
    def handle(self, *args, **options):
        force = options["force"]
        created_total = 0

        # --- usages --------------------------------------------------------
        usages = {}
        for name, label, order in USAGES:
            obj, created = self._upsert(
                PropertyUsage, name,
                {"display_name": label, "sort_order": Decimal(order)}, force,
            )
            usages[name] = obj
            created_total += created
        self.stdout.write(f"  کاربری ملک        : {len(usages)}")

        # --- property types -------------------------------------------------
        types = {}
        for name, label, usage, order in PROPERTY_TYPES:
            obj, created = self._upsert(
                PropertyType, name,
                {
                    "display_name": label,
                    "property_usage": usages[usage],
                    "sort_order": Decimal(order),
                    "slug": name,
                },
                force,
            )
            types[name] = obj
            created_total += created
        self.stdout.write(f"  انواع ملک         : {len(types)}")

        # --- deal types -----------------------------------------------------
        deals = {}
        for name, label, order in DEAL_TYPES:
            obj, created = self._upsert(
                DealType, name,
                {"display_name": label, "sort_order": Decimal(order)}, force,
            )
            deals[name] = obj
            created_total += created
        self.stdout.write(f"  انواع معامله      : {len(deals)}")

        # --- attributes ------------------------------------------------------
        attrs = {}
        for (
            name, label, data_type, filter_type, unit, entity,
            is_facility, is_core, core_field, order,
        ) in ATTRIBUTES:
            obj, created = self._upsert(
                Attribute, name,
                {
                    "display_name": label,
                    "data_type": data_type,
                    "filter_type": filter_type,
                    "unit": unit,
                    "entity": entity,
                    "is_facility": is_facility,
                    "is_core": is_core,
                    "core_field": core_field,
                    "sort_order": Decimal(order),
                },
                force,
            )
            attrs[name] = obj
            created_total += created
        self.stdout.write(f"  ویژگی‌ها          : {len(attrs)}")

        # --- options for select attributes ------------------------------------
        option_count = 0
        for attr_name, options in ATTRIBUTE_OPTIONS.items():
            attribute = attrs[attr_name]
            for value, label, order in options:
                _, created = AttributeOption.all_objects.update_or_create(
                    attribute=attribute,
                    value=value,
                    defaults={"display_name": label, "sort_order": Decimal(order)},
                )
                option_count += 1
        self.stdout.write(f"  گزینه‌های ویژگی   : {option_count}")

        # --- bind attributes to property types --------------------------------
        shared = TYPE_ATTRIBUTES.get("*", [])
        link_count = 0
        for type_name, type_obj in types.items():
            entries = shared + TYPE_ATTRIBUTES.get(type_name, [])
            for position, (attr_name, required) in enumerate(entries, start=1):
                PropertyTypeAttribute.objects.update_or_create(
                    property_type=type_obj,
                    attribute=attrs[attr_name],
                    defaults={
                        "is_required": required,
                        "sort_order": Decimal(position * 10),
                        "is_active": True,
                    },
                )
                link_count += 1
        self.stdout.write(f"  اتصال ویژگی به نوع ملک: {link_count}")

        # --- search filters ----------------------------------------------------
        shared_search = TYPE_SEARCH_ATTRIBUTES.get("*", [])
        search_count = 0
        for type_name, type_obj in types.items():
            entries = shared_search + TYPE_SEARCH_ATTRIBUTES.get(type_name, [])
            for position, attr_name in enumerate(entries, start=1):
                PropertyTypeSearchAttribute.objects.update_or_create(
                    property_type=type_obj,
                    attribute=attrs[attr_name],
                    defaults={"sort_order": Decimal(position * 10), "is_active": True},
                )
                search_count += 1
        self.stdout.write(f"  فیلترهای جستجو    : {search_count}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nاطلاعات پایه آماده شد ({created_total} رکورد جدید ایجاد شد)."
            )
        )
