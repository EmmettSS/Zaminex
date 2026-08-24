"""Reference data ("اطلاعات پایه") and the dynamic attribute engine.

Why this app exists
-------------------
Property usage, property type and deal type used to be hard-coded
``TextChoices`` in Python. Adding "سوئیت" or "پیش‌فروش" meant editing code and
redeploying. They are now database rows an administrator maintains from the UI.

On top of that sits the attribute engine the client asked for:

    Attribute                     e.g. "تعداد اتاق" (integer), "پارکینگ" (boolean)
      ↓ linked to
    PropertyType / DealType       via PropertyTypeAttribute / DealTypeAttribute
      ↓ produces
    a dynamic form                only the attributes that apply are shown
      ↓ stored in
    PropertyAttributeValue        (see apps/properties/models.py)
    ListingAttributeValue         (see apps/listings/models.py)

So "تعداد اتاق" can be attached to آپارتمان but not to زمین, exactly as the
client described.

Core vs. dynamic attributes
---------------------------
An attribute may be marked ``is_core``. Core attributes are *not* stored in the
EAV tables — they map to a real, indexed column on Property or Listing
(``area``, ``sale_price``, ``deposit`` ...). This is the hybrid model the client
asked for: fields that drive search stay fast columns, everything else is
flexible EAV. ``core_field`` records which column an attribute maps to.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.common.base_models import ReferenceDataModel, SoftDeleteModel


class PropertyUsage(ReferenceDataModel):
    """How a property is used: مسکونی / تجاری / اداری.

    The broadest classification. Every PropertyType belongs to exactly one
    usage, so the "افزودن ملک" form can cascade usage → type.
    """

    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_property_usage"
        constraints = [ReferenceDataModel.alive_name_unique("property_usage")]
        verbose_name = "کاربری ملک"
        verbose_name_plural = "کاربری‌های ملک"
        ordering = ["sort_order", "display_name"]


class PropertyType(ReferenceDataModel):
    """A concrete kind of property: آپارتمان، ویلا، مغازه، زمین …

    ``slug`` mirrors the client's schema and is reserved for public URLs; it is
    optional and unused by the CRM today.
    """

    property_usage = models.ForeignKey(
        PropertyUsage,
        on_delete=models.PROTECT,
        related_name="property_types",
        verbose_name="کاربری ملک",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        allow_unicode=True,
        verbose_name="اسلاگ",
    )
    attributes = models.ManyToManyField(
        "basics.Attribute",
        through="basics.PropertyTypeAttribute",
        related_name="property_types",
        verbose_name="ویژگی‌ها",
    )

    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_property_type"
        constraints = [ReferenceDataModel.alive_name_unique("property_type")]
        verbose_name = "نوع ملک"
        verbose_name_plural = "انواع ملک"
        ordering = ["sort_order", "display_name"]
        indexes = [models.Index(fields=["property_usage", "sort_order"])]


class DealType(ReferenceDataModel):
    """A kind of transaction: فروش، رهن و اجاره، پیش‌فروش …

    Deal type lives on the *listing*, never on the property: one property can be
    advertised for sale and for rent at the same time.
    """

    attributes = models.ManyToManyField(
        "basics.Attribute",
        through="basics.DealTypeAttribute",
        related_name="deal_types",
        verbose_name="ویژگی‌ها",
    )

    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_deal_type"
        constraints = [ReferenceDataModel.alive_name_unique("deal_type")]
        verbose_name = "نوع معامله"
        verbose_name_plural = "انواع معامله"
        ordering = ["sort_order", "display_name"]


class Attribute(ReferenceDataModel):
    """A custom field an administrator defines once and reuses everywhere."""

    class DataType(models.TextChoices):
        TEXT = "text", "متن"
        INTEGER = "integer", "عدد صحیح"
        DECIMAL = "decimal", "عدد اعشاری"
        BOOLEAN = "boolean", "بله / خیر"
        DATE = "date", "تاریخ"
        SELECT = "select", "انتخاب یکی"
        MULTISELECT = "multiselect", "انتخاب چندتایی"

    class InputType(models.TextChoices):
        DEFAULT = "default", "پیش‌فرض"
        PRICE = "price", "مبلغ"

    class FilterType(models.TextChoices):
        NONE = "none", "بدون فیلتر"
        EXACT = "exact", "تطابق دقیق"
        RANGE = "range", "بازه‌ای"
        RANGE_FAST = "range_fast", "بازه‌ای (سریع)"
        EXISTS = "exists", "وجود دارد"

    class Entity(models.TextChoices):
        """Which side of the model an attribute describes.

        Physical facts about the building belong to the property; commercial
        terms belong to the listing. Keeping them apart stops "مبلغ رهن" from
        being offered on the property form.
        """

        PROPERTY = "property", "ملک"
        LISTING = "listing", "آگهی"

    data_type = models.CharField(
        max_length=20,
        choices=DataType.choices,
        verbose_name="نوع داده",
    )
    input_type = models.CharField(
        max_length=20,
        choices=InputType.choices,
        default=InputType.DEFAULT,
        verbose_name="نوع ورودی",
        help_text="«مبلغ» باعث نمایش جداکننده هزارگان در فرم می‌شود.",
    )
    filter_type = models.CharField(
        max_length=20,
        choices=FilterType.choices,
        default=FilterType.NONE,
        verbose_name="نوع فیلتر",
    )
    entity = models.CharField(
        max_length=20,
        choices=Entity.choices,
        default=Entity.PROPERTY,
        db_index=True,
        verbose_name="مربوط به",
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="واحد",
        help_text="مثلاً متر مربع، تومان، عدد.",
    )
    is_facility = models.BooleanField(
        default=False,
        verbose_name="امکانات رفاهی",
        help_text="ویژگی‌های بله/خیر مانند آسانسور و پارکینگ که به صورت گروهی نمایش داده می‌شوند.",
    )

    # --- hybrid storage -----------------------------------------------------
    is_core = models.BooleanField(
        default=False,
        verbose_name="فیلد ثابت",
        help_text=(
            "ویژگی‌های ثابت در ستون اختصاصی و ایندکس‌شده ذخیره می‌شوند (مانند متراژ و قیمت) "
            "و در جستجو سریع‌تر هستند. بقیه ویژگی‌ها به صورت پویا ذخیره می‌شوند."
        ),
    )
    core_field = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="نام ستون ثابت",
        help_text="نام فیلد مدل که این ویژگی به آن نگاشت می‌شود (فقط برای فیلدهای ثابت).",
    )

    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_attribute"
        constraints = [ReferenceDataModel.alive_name_unique("attribute")]
        verbose_name = "ویژگی"
        verbose_name_plural = "ویژگی‌ها"
        ordering = ["sort_order", "display_name"]
        indexes = [
            models.Index(fields=["entity", "sort_order"]),
            models.Index(
                fields=["is_facility"],
                condition=models.Q(is_facility=True),
                name="idx_attribute_facility",
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_core and not self.core_field:
            raise ValidationError(
                {"core_field": "برای ویژگی ثابت باید نام ستون مربوطه مشخص شود."}
            )
        if not self.is_core and self.core_field:
            raise ValidationError(
                {"core_field": "نام ستون ثابت فقط برای ویژگی‌های ثابت معنا دارد."}
            )
        if self.data_type in {self.DataType.SELECT, self.DataType.MULTISELECT}:
            # Options are validated on save of the related rows; a select with
            # no options would render an empty dropdown.
            if self.pk and not self.options.exists():
                raise ValidationError(
                    {"data_type": "برای ویژگی انتخابی باید حداقل یک گزینه تعریف شود."}
                )

    @property
    def value_field(self) -> str:
        """Which column of the EAV value table holds this attribute's data."""
        return {
            self.DataType.TEXT: "value_text",
            self.DataType.INTEGER: "value_integer",
            self.DataType.DECIMAL: "value_decimal",
            self.DataType.BOOLEAN: "value_boolean",
            self.DataType.DATE: "value_date",
            self.DataType.SELECT: "value_text",
            self.DataType.MULTISELECT: "value_json",
        }[self.data_type]


class AttributeOption(SoftDeleteModel):
    """A choice for a ``select`` / ``multiselect`` attribute.

    The client's schema stores these inside ``meta_data``. A real table is used
    instead so options can be reordered, deactivated and referenced by a stable
    key, and so a typo in one row cannot corrupt the whole option list.
    """

    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name="ویژگی",
    )
    value = models.CharField(
        max_length=100,
        verbose_name="مقدار",
        help_text="کلید ذخیره‌شده در پایگاه داده (انگلیسی و ثابت).",
    )
    display_name = models.CharField(max_length=255, verbose_name="نام نمایشی")
    sort_order = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="ترتیب نمایش"
    )

    class Meta:
        db_table = "basics_attribute_option"
        verbose_name = "گزینه ویژگی"
        verbose_name_plural = "گزینه‌های ویژگی"
        ordering = ["sort_order", "display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["attribute", "value"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_attribute_option_value_alive",
            )
        ]

    def __str__(self):
        return f"{self.attribute.display_name} — {self.display_name}"


class AttributeLink(models.Model):
    """Shared columns for the four attribute-binding tables."""

    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        verbose_name="ویژگی",
    )
    sort_order = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="ترتیب نمایش"
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        abstract = True


class PropertyTypeAttribute(AttributeLink):
    """Which attributes appear on the "افزودن ملک" form for a property type."""

    property_type = models.ForeignKey(
        PropertyType,
        on_delete=models.CASCADE,
        related_name="attribute_links",
        verbose_name="نوع ملک",
    )
    is_required = models.BooleanField(default=False, verbose_name="اجباری")

    class Meta:
        db_table = "basics_property_type_attribute"
        verbose_name = "ویژگی نوع ملک"
        verbose_name_plural = "ویژگی‌های نوع ملک"
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["property_type", "attribute"],
                name="uq_property_type_attribute",
            )
        ]
        indexes = [models.Index(fields=["property_type", "is_active", "sort_order"])]

    def __str__(self):
        return f"{self.property_type.display_name} → {self.attribute.display_name}"

    def clean(self):
        super().clean()
        if self.attribute_id and self.attribute.entity != Attribute.Entity.PROPERTY:
            raise ValidationError(
                {"attribute": "فقط ویژگی‌های مربوط به ملک را می‌توان به نوع ملک متصل کرد."}
            )


class DealTypeAttribute(AttributeLink):
    """Which attributes appear on the "ساخت آگهی" form for a deal type."""

    deal_type = models.ForeignKey(
        DealType,
        on_delete=models.CASCADE,
        related_name="attribute_links",
        verbose_name="نوع معامله",
    )
    is_required = models.BooleanField(default=False, verbose_name="اجباری")

    class Meta:
        db_table = "basics_deal_type_attribute"
        verbose_name = "ویژگی نوع معامله"
        verbose_name_plural = "ویژگی‌های نوع معامله"
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["deal_type", "attribute"],
                name="uq_deal_type_attribute",
            )
        ]
        indexes = [models.Index(fields=["deal_type", "is_active", "sort_order"])]

    def __str__(self):
        return f"{self.deal_type.display_name} → {self.attribute.display_name}"

    def clean(self):
        super().clean()
        if self.attribute_id and self.attribute.entity != Attribute.Entity.LISTING:
            raise ValidationError(
                {"attribute": "فقط ویژگی‌های مربوط به آگهی را می‌توان به نوع معامله متصل کرد."}
            )


class PropertyTypeSearchAttribute(AttributeLink):
    """Which attributes appear as *search filters* for a property type.

    Separate from :class:`PropertyTypeAttribute` because the data an agent
    records is not the same set they filter by: "توضیحات مالک" is worth storing
    but useless as a filter, while "متراژ" is a core column that belongs in the
    filter bar without being a dynamic form field.
    """

    property_type = models.ForeignKey(
        PropertyType,
        on_delete=models.CASCADE,
        related_name="search_attribute_links",
        verbose_name="نوع ملک",
    )

    class Meta:
        db_table = "basics_property_type_search_attribute"
        verbose_name = "فیلتر جستجوی نوع ملک"
        verbose_name_plural = "فیلترهای جستجوی نوع ملک"
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["property_type", "attribute"],
                name="uq_property_type_search_attribute",
            )
        ]
        indexes = [models.Index(fields=["property_type", "is_active", "sort_order"])]

    def __str__(self):
        return f"{self.property_type.display_name} ⌕ {self.attribute.display_name}"


class DealTypeSearchAttribute(AttributeLink):
    """Which attributes appear as *search filters* for a deal type."""

    deal_type = models.ForeignKey(
        DealType,
        on_delete=models.CASCADE,
        related_name="search_attribute_links",
        verbose_name="نوع معامله",
    )

    class Meta:
        db_table = "basics_deal_type_search_attribute"
        verbose_name = "فیلتر جستجوی نوع معامله"
        verbose_name_plural = "فیلترهای جستجوی نوع معامله"
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["deal_type", "attribute"],
                name="uq_deal_type_search_attribute",
            )
        ]
        indexes = [models.Index(fields=["deal_type", "is_active", "sort_order"])]

    def __str__(self):
        return f"{self.deal_type.display_name} ⌕ {self.attribute.display_name}"


# ---------------------------------------------------------------------------
#  Geography: Province → City → District
# ---------------------------------------------------------------------------
#
# Replaces the old flat `common.District` table (a single free-text name) with
# the three-level hierarchy the client's schema describes. Every level is
# administrator-managed: no province, city or district is seeded, because the
# agency knows its own coverage area and a shipped list would be wrong for them.
#
# `Property.district` becomes a foreign key here, so a neighbourhood can be
# renamed once and every property follows, and so filtering by city no longer
# depends on matching free text.


class Province(ReferenceDataModel):
    """A province (استان)."""

    slug = models.SlugField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        allow_unicode=True,
        verbose_name="اسلاگ",
    )

    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_province"
        constraints = [ReferenceDataModel.alive_name_unique("province")]
        verbose_name = "استان"
        verbose_name_plural = "استان‌ها"
        ordering = ["sort_order", "display_name"]


class City(ReferenceDataModel):
    """A city (شهر), belonging to exactly one province."""

    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        related_name="cities",
        verbose_name="استان",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        allow_unicode=True,
        verbose_name="اسلاگ",
    )

    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_city"
        # `name` is only unique within its province: two provinces may each
        # have a "مرکزی" without clashing.
        constraints = [
            models.UniqueConstraint(
                fields=["province", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_city_name_per_province_alive",
            )
        ]
        verbose_name = "شهر"
        verbose_name_plural = "شهرها"
        ordering = ["sort_order", "display_name"]
        indexes = [models.Index(fields=["province", "sort_order"])]


class District(ReferenceDataModel):
    """A neighbourhood (محله), belonging to exactly one city."""

    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="districts",
        verbose_name="شهر",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        allow_unicode=True,
        verbose_name="اسلاگ",
    )

    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_district"
        constraints = [
            models.UniqueConstraint(
                fields=["city", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_district_name_per_city_alive",
            )
        ]
        verbose_name = "محله"
        verbose_name_plural = "محله‌ها"
        ordering = ["sort_order", "display_name"]
        indexes = [models.Index(fields=["city", "sort_order"])]

    @property
    def full_path(self) -> str:
        """"استان / شهر / محله" — used wherever the district is shown alone."""
        return f"{self.city.province.display_name} / {self.city.display_name} / {self.display_name}"
