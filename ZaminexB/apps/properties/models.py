from django.db import models

from .validators import validate_property_image
from django.conf import settings

from apps.common.attribute_values import BaseAttributeValue


class ActivePropertyManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(status=Property.Status.INACTIVE)


class Property(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        RESERVED = "RESERVED", "Reserved"
        SOLD = "SOLD", "Sold"
        INACTIVE = "INACTIVE", "Archived"

    class DealType(models.TextChoices):
        SALE = "SALE", "Sale"
        RENT = "RENT", "Rent"

    class PropertyType(models.TextChoices):
        APARTMENT = "APARTMENT", "Apartment"
        VILLA = "VILLA", "Villa"
        TOWNHOUSE = "TOWNHOUSE", "Townhouse"
        STUDIO = "STUDIO", "Studio"
        PENTHOUSE = "PENTHOUSE", "Penthouse"
        COMMERCIAL = "COMMERCIAL", "Commercial"
        OFFICE = "OFFICE", "Office"
        SHOP = "SHOP", "Shop"
        LAND = "LAND", "Land"
        OTHER = "OTHER", "Other"

    title = models.CharField(max_length=255, verbose_name="عنوان ملک")
    internal_code = models.CharField(max_length=50, unique=True, verbose_name="کد داخلی")

    consultant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="properties",
        limit_choices_to={"role": "AGENT"},
        verbose_name="مشاور مسئول",
    )

    # Legacy hard-coded column. Superseded by `property_type_ref` below and
    # removed once every reader has been migrated; kept in place for now so
    # this phase changes no behaviour. See apps/basics/models.py.
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        verbose_name="نوع ملک (قدیمی)",
    )

    # --- reference data (phase 2) ------------------------------------------
    # Nullable during the transition: existing rows are backfilled by the
    # `link_properties_to_basics` command, and the columns above stay
    # authoritative until phase 3 switches the readers over.
    property_usage = models.ForeignKey(
        "basics.PropertyUsage",
        on_delete=models.PROTECT,
        related_name="properties",
        null=True,
        blank=True,
        verbose_name="کاربری ملک",
    )
    property_type_ref = models.ForeignKey(
        "basics.PropertyType",
        on_delete=models.PROTECT,
        related_name="properties",
        null=True,
        blank=True,
        verbose_name="نوع ملک",
    )

    deal_type = models.CharField(
        max_length=20,
        choices=DealType.choices,
        verbose_name="نوع معامله",
    )

    # Deprecated. Pricing belongs to the listing (Listing.sale_price / deposit
    # / monthly_rent) because one property can be advertised for sale and for
    # rent at once.
    #
    # Nothing reads this column directly any more: every caller goes through
    # `apps.common.metrics.effective_sale_price`, which prefers the property's
    # sale listings and only falls back here for records created before the
    # split. It is retained so those historical figures stay readable, and can
    # be dropped once no row relies on the fallback.
    price = models.DecimalField(
        max_digits=18,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="قیمت (منسوخ — در آگهی ثبت می‌شود)",
    )
    area = models.PositiveIntegerField(verbose_name="مساحت")
    rooms = models.PositiveIntegerField(default=0, verbose_name="تعداد خواب")
    floor = models.IntegerField(null=True, blank=True, verbose_name="طبقه")
    built_year = models.PositiveIntegerField(null=True, blank=True, verbose_name="سال ساخت")

    address = models.TextField(verbose_name="آدرس کامل")
    # Legacy free-text neighbourhood. Superseded by the `district` foreign key
    # below; still written on save so existing readers, search filters and the
    # market-metrics grouping keep working unchanged.
    neighborhood = models.CharField(
        max_length=255, blank=True, verbose_name="محله / منطقه (متنی)"
    )

    # --- location (phase 4) -------------------------------------------------
    # Province and city are reachable through `district.city.province`, so only
    # the leaf is stored. Nullable during the transition: existing rows are
    # backfilled by `migrate_districts_to_hierarchy`.
    district = models.ForeignKey(
        "basics.District",
        on_delete=models.PROTECT,
        related_name="properties",
        null=True,
        blank=True,
        verbose_name="محله",
    )
    description = models.TextField(blank=True, verbose_name="توضیحات")

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="عرض جغرافیایی",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="طول جغرافیایی",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        verbose_name="وضعیت",
    )

    is_shared = models.BooleanField(
        default=False,
        verbose_name="نمایش برای همه مشاوران",
        help_text="وقتی فعال باشد، همه مشاوران ملک را می‌بینند و می‌توانند ویرایش کنند (به جز تغییر مشاور مسئول).",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    objects = models.Manager()
    active_objects = ActivePropertyManager()

    class Meta:
        verbose_name = "ملک"
        verbose_name_plural = "املاک"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Mirror the linked district's name into the legacy text column.

        Reports, the market-metrics grouping and the existing search filter all
        read `neighborhood`. Keeping it in step means the foreign key can be
        introduced without touching any of them, and a district renamed by an
        administrator propagates to its properties on their next save.
        """
        if self.district_id:
            name = self.district.display_name
            if self.neighborhood != name:
                self.neighborhood = name
                update_fields = kwargs.get("update_fields")
                if update_fields is not None and "neighborhood" not in update_fields:
                    kwargs["update_fields"] = list(update_fields) + ["neighborhood"]
        super().save(*args, **kwargs)


class PropertyAttributeValue(BaseAttributeValue):
    """A dynamic attribute value for one property.

    Only non-core attributes land here; core ones (متراژ، تعداد اتاق …) live in
    real columns on :class:`Property` so they stay fast to filter on.
    """

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="attribute_values",
        verbose_name="ملک",
    )

    class Meta:
        db_table = "properties_property_attribute_value"
        verbose_name = "مقدار ویژگی ملک"
        verbose_name_plural = "مقادیر ویژگی ملک"
        constraints = [
            models.UniqueConstraint(
                fields=["property", "attribute"],
                name="uq_property_attribute_value",
            )
        ]
        indexes = [
            # One index per typed column: filtering by a dynamic attribute
            # always narrows on attribute_id first, then the matching value.
            models.Index(fields=["attribute", "value_integer"], name="idx_pav_attr_int"),
            models.Index(fields=["attribute", "value_decimal"], name="idx_pav_attr_dec"),
            models.Index(fields=["attribute", "value_boolean"], name="idx_pav_attr_bool"),
            models.Index(fields=["attribute", "value_date"], name="idx_pav_attr_date"),
        ]


class PropertyImage(models.Model):
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="ملک",
    )
    image = models.ImageField(
        upload_to="properties/images/",
        verbose_name="تصویر",
        validators=[validate_property_image],
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "تصویر ملک"
        verbose_name_plural = "تصاویر ملک"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.property.title} - Image {self.pk}"