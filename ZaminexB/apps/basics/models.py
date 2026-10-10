from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.common.base_models import ReferenceDataModel, SoftDeleteModel

from .categorization import ESSENTIAL as ESSENTIAL_CATEGORY
from .categorization import NON_ESSENTIAL as NON_ESSENTIAL_CATEGORY


class PropertyUsage(ReferenceDataModel):
    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_property_usage"
        constraints = [ReferenceDataModel.alive_name_unique("property_usage")]
        verbose_name = "کاربری ملک"
        verbose_name_plural = "کاربری‌های ملک"
        ordering = ["sort_order", "display_name"]


class PropertyType(ReferenceDataModel):
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


class AttributeCategory(ReferenceDataModel):
    class Meta(ReferenceDataModel.Meta):
        abstract = False
        db_table = "basics_attribute_category"
        constraints = [ReferenceDataModel.alive_name_unique("attribute_category")]
        verbose_name = "دسته‌بندی ویژگی"
        verbose_name_plural = "دسته‌بندی‌های ویژگی"
        ordering = ["sort_order", "display_name"]

    @property
    def is_system_category(self) -> bool:
        return self.name in (ESSENTIAL_CATEGORY, NON_ESSENTIAL_CATEGORY)

    def attribute_count(self) -> int:
        return Attribute.objects.filter(category=self.name).count()


class Attribute(ReferenceDataModel):
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
        PROPERTY = "property", "ملک"
        LISTING = "listing", "آگهی"

    class Category(models.TextChoices):
        ESSENTIAL = ESSENTIAL_CATEGORY, "ویژگی ضروری"
        NON_ESSENTIAL = NON_ESSENTIAL_CATEGORY, "ویژگی غیر ضروری"

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
    
    category = models.CharField(
        max_length=100,
        default=Category.NON_ESSENTIAL,
        db_index=True,
        verbose_name="دسته‌بندی ویژگی",
        help_text=(
            "دسته‌بندی‌ای که این ویژگی در آن قرار می‌گیرد؛ فهرست دسته‌بندی‌ها از "
            "تب «دسته‌بندی ویژگی‌ها» مدیریت می‌شود. یک ویژگی همیشه دقیقاً در یک "
            "دسته‌بندی قرار دارد."
        ),
    )
    is_facility = models.BooleanField(
        default=False,
        verbose_name="امکانات رفاهی",
        help_text="ویژگی‌های بله/خیر مانند آسانسور و پارکینگ که به صورت گروهی نمایش داده می‌شوند.",
    )

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
            if self.pk and not self.options.exists():
                raise ValidationError(
                    {"data_type": "برای ویژگی انتخابی باید حداقل یک گزینه تعریف شود."}
                )

    @property
    def value_field(self) -> str:
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


class Province(ReferenceDataModel):
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
        return f"{self.city.province.display_name} / {self.city.display_name} / {self.display_name}"
