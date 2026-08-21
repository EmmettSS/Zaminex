from django.db import models
from django.conf import settings

from apps.common.attribute_values import BaseAttributeValue


class Listing(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        SOLD = "SOLD", "Sold"
        EXPIRED = "EXPIRED", "Expired"
        ARCHIVED = "ARCHIVED", "Archived"

    class PublishChannel(models.TextChoices):
        WEBSITE = "WEBSITE", "Website"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        TELEGRAM = "TELEGRAM", "Telegram"
        OTHER = "OTHER", "Other"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        NORMAL = 2, "Normal"
        HIGH = 3, "High"
        URGENT = 4, "Urgent"

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="listings",
        verbose_name="ملک",
    )

    # --- reference data (phase 2) ------------------------------------------
    # Deal type belongs to the listing, not the property: the same property can
    # be advertised for sale and for rent simultaneously. Nullable during the
    # transition; backfilled from Property.deal_type by
    # `link_properties_to_basics`, and made mandatory in phase 4 when pricing
    # moves onto the listing.
    deal_type = models.ForeignKey(
        "basics.DealType",
        on_delete=models.PROTECT,
        related_name="listings",
        null=True,
        blank=True,
        verbose_name="نوع معامله",
    )

    title = models.CharField(max_length=255, verbose_name="عنوان آگهی")
    description = models.TextField(blank=True, verbose_name="توضیحات")

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="وضعیت",
    )

    publish_channel = models.CharField(
        max_length=30,
        choices=PublishChannel.choices,
        verbose_name="کانال انتشار",
    )

    start_date = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ شروع")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ پایان")

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_listings",
        verbose_name="مسئول آگهی",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_listings",
        verbose_name="ایجاد کننده",
    )

    priority = models.IntegerField(
        choices=Priority.choices,
        default=Priority.NORMAL,
        verbose_name="اولویت",
    )

    is_featured = models.BooleanField(default=False, verbose_name="آگهی ویژه")

    # --- pricing (phase 3) --------------------------------------------------
    # Money lives on the listing, not the property: the same property can be
    # advertised for sale and for rent at the same time, at different prices.
    #
    # These are real indexed columns rather than EAV rows because price is the
    # single most common search filter — a range query has to stay fast. Which
    # of them a given deal type uses is configured through DealTypeAttribute,
    # so "مبلغ رهن" only appears for رهن و اجاره.
    sale_price = models.DecimalField(
        max_digits=18,
        decimal_places=0,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="قیمت فروش",
    )
    deposit = models.DecimalField(
        max_digits=18,
        decimal_places=0,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="مبلغ رهن / ودیعه",
    )
    monthly_rent = models.DecimalField(
        max_digits=18,
        decimal_places=0,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="اجاره ماهانه",
    )
    # Open-ended pricing detail (instalment plans, staged presale payments …)
    # mirroring `price_details JSONB` in the client's schema.
    price_details = models.JSONField(
        default=dict, blank=True, verbose_name="جزئیات قیمت"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "آگهی"
        verbose_name_plural = "آگهی‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ListingAttributeValue(BaseAttributeValue):
    """A dynamic attribute value for one listing.

    Holds the commercial terms that vary per deal type — deposit, monthly rent,
    presale instalments — for everything that is not a core indexed column.
    """

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="attribute_values",
        verbose_name="آگهی",
    )

    class Meta:
        db_table = "listings_listing_attribute_value"
        verbose_name = "مقدار ویژگی آگهی"
        verbose_name_plural = "مقادیر ویژگی آگهی"
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "attribute"],
                name="uq_listing_attribute_value",
            )
        ]
        indexes = [
            models.Index(fields=["attribute", "value_integer"], name="idx_lav_attr_int"),
            models.Index(fields=["attribute", "value_decimal"], name="idx_lav_attr_dec"),
            models.Index(fields=["attribute", "value_boolean"], name="idx_lav_attr_bool"),
            models.Index(fields=["attribute", "value_date"], name="idx_lav_attr_date"),
        ]
