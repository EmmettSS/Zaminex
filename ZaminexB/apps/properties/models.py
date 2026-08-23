import os
import uuid

from django.db import models

from .validators import validate_appraisal_pdf, validate_property_image
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

    # --- owner contact (اطلاعات مالک) --------------------------------------
    # Fields are nullable at the database level so historical rows and the
    # REST API stay compatible during the transition; the write path enforces
    # them (the create serializer and the front-end form require them).
    owner_first_name = models.CharField(
        max_length=100, blank=True, default="", verbose_name="نام مالک"
    )
    owner_last_name = models.CharField(
        max_length=100, blank=True, default="", verbose_name="نام خانوادگی مالک"
    )
    owner_phone = models.CharField(
        max_length=20, blank=True, default="", verbose_name="شماره موبایل مالک"
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
        """Mirror the linked district's name into the legacy text column and
        auto-generate the sequential internal_code for new instances.
        """
        if self.pk is None:
            # Auto-generate sequential internal_code for new properties
            if not self.internal_code or not str(self.internal_code).startswith("ZF_"):
                self.internal_code = _generate_next_internal_code()

        if self.district_id:
            name = self.district.display_name
            if self.neighborhood != name:
                self.neighborhood = name
                update_fields = kwargs.get("update_fields")
                if update_fields is not None and "neighborhood" not in update_fields:
                    kwargs["update_fields"] = list(update_fields) + ["neighborhood"]
        super().save(*args, **kwargs)


def _generate_next_internal_code():
    """Generate the next sequential ZF_XXXX internal code.

    Sequence rules:
    - Starts at ZF_1111
    - Only digits 1-9 (no zero allowed anywhere)
    - Increases sequentially; skips any value containing digit 0
    - Always globally unique
    """
    existing = (
        Property.objects.filter(internal_code__regex=r"^ZF_[1-9]{4}$")
        .values_list("internal_code", flat=True)
    )

    max_val = 1110  # one below starting value
    for code in existing:
        try:
            val = int(str(code)[3:])
            if val > max_val:
                max_val = val
        except (ValueError, IndexError):
            continue

    next_val = max_val + 1
    while "0" in str(next_val):
        next_val += 1

    # Commercial-grade safeguard: expand to 5 digits if 4-digit space is exhausted
    if next_val > 99999:
        raise RuntimeError("فضای کدهای داخلی به پایان رسیده است.")

    next_str = f"{next_val:04d}" if next_val <= 9999 else f"{next_val:05d}"
    return f"ZF_{next_str}"


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


def appraisal_report_upload_path(instance, filename):
    """Storage path for an appraisal PDF.

    The stored name is random and URL-safe (Persian/space-laden original
    names cause needless trouble on filesystems and in URLs); the
    user-facing name is preserved in ``original_filename`` and used for the
    download's Content-Disposition instead.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext != ".pdf":
        ext = ".pdf"
    return f"properties/appraisals/{instance.property_id}/{uuid.uuid4().hex}{ext}"


class PropertyAppraisalReport(models.Model):
    """The single PDF appraisal report (گزارش کارشناسی) attached to a property.

    One report per property — the OneToOneField enforces that at the
    database level. Uploading again replaces the previous row and its file
    (see ``PropertyViewSet.appraisal_report``), so exactly one PDF exists at
    any time and no orphaned files are left behind.
    """

    property = models.OneToOneField(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="appraisal_report",
        verbose_name="ملک",
    )
    file = models.FileField(
        upload_to=appraisal_report_upload_path,
        validators=[validate_appraisal_pdf],
        verbose_name="فایل گزارش کارشناسی",
        help_text="فقط فایل PDF، حداکثر ۱۰ مگابایت.",
    )
    # Kept apart from the stored path so downloads keep the name the
    # consultant chose, while storage stays URL-safe.
    original_filename = models.CharField(max_length=255, verbose_name="نام اصلی فایل")
    file_size = models.PositiveIntegerField(verbose_name="حجم فایل (بایت)")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_appraisal_reports",
        verbose_name="بارگذاری‌کننده",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "گزارش کارشناسی ملک"
        verbose_name_plural = "گزارش‌های کارشناسی ملک"

    def __str__(self):
        return f"{self.property.title} - {self.original_filename}"

    def delete(self, *args, **kwargs):
        # Remove the row first, then the stored PDF: if the database delete
        # fails the file is left untouched (no dangling row), while a failed
        # file delete can at worst leave an orphan on disk. FileSystemStorage
        # treats a missing file as a no-op, so this never raises on re-runs.
        pk = self.pk
        super().delete(*args, **kwargs)
        if pk is not None:
            self.file.delete(save=False)