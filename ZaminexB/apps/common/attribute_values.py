"""Shared base for the EAV value tables.

``PropertyAttributeValue`` and ``ListingAttributeValue`` are structurally
identical — only the owning foreign key differs — so the columns, the typed
read/write helpers and the validation live here.

One row holds one attribute's value for one record. Which column is populated
depends on the attribute's ``data_type``; the rest stay NULL. This keeps values
correctly typed (so ``value_integer >= 3`` is a real numeric comparison, not a
string one) and lets each column carry its own index.
"""

from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models


class AttributeValueQuerySet(models.QuerySet):
    def for_attribute(self, name: str):
        return self.filter(attribute__name=name)


class BaseAttributeValue(models.Model):
    """One attribute value, stored in the column matching its data type."""

    attribute = models.ForeignKey(
        "basics.Attribute",
        on_delete=models.CASCADE,
        verbose_name="ویژگی",
    )

    value_text = models.TextField(null=True, blank=True, verbose_name="مقدار متنی")
    value_integer = models.BigIntegerField(null=True, blank=True, verbose_name="مقدار عددی")
    value_decimal = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True, verbose_name="مقدار اعشاری"
    )
    value_boolean = models.BooleanField(null=True, blank=True, verbose_name="مقدار بله/خیر")
    value_date = models.DateField(null=True, blank=True, verbose_name="مقدار تاریخ")
    value_json = models.JSONField(null=True, blank=True, verbose_name="مقدار چندتایی")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    objects = AttributeValueQuerySet.as_manager()

    class Meta:
        abstract = True

    # -- typed access -------------------------------------------------------

    @property
    def value(self):
        """The populated value, whatever its type."""
        return getattr(self, self.attribute.value_field)

    @value.setter
    def value(self, raw):
        self.set_value(raw)

    def set_value(self, raw):
        """Coerce ``raw`` into the column matching the attribute's data type.

        Input arrives as strings from JSON and HTML forms, so each branch
        parses defensively and reports a Persian error the UI can display
        as-is.
        """
        from apps.basics.models import Attribute

        # Start clean: switching an attribute's type must not leave a stale
        # value behind in the previous column.
        for field in (
            "value_text", "value_integer", "value_decimal",
            "value_boolean", "value_date", "value_json",
        ):
            setattr(self, field, None)

        if raw is None or raw == "":
            return

        data_type = self.attribute.data_type
        label = self.attribute.display_name

        if data_type == Attribute.DataType.TEXT:
            self.value_text = str(raw)

        elif data_type == Attribute.DataType.INTEGER:
            try:
                self.value_integer = int(str(raw).strip().replace(",", ""))
            except (TypeError, ValueError):
                raise ValidationError({self.attribute.name: f"«{label}» باید عدد صحیح باشد."})

        elif data_type == Attribute.DataType.DECIMAL:
            try:
                self.value_decimal = Decimal(str(raw).strip().replace(",", ""))
            except (TypeError, ValueError, InvalidOperation):
                raise ValidationError({self.attribute.name: f"«{label}» باید عدد باشد."})

        elif data_type == Attribute.DataType.BOOLEAN:
            if isinstance(raw, bool):
                self.value_boolean = raw
            else:
                token = str(raw).strip().lower()
                if token in {"true", "1", "yes", "on", "بله"}:
                    self.value_boolean = True
                elif token in {"false", "0", "no", "off", "خیر"}:
                    self.value_boolean = False
                else:
                    raise ValidationError(
                        {self.attribute.name: f"«{label}» باید بله یا خیر باشد."}
                    )

        elif data_type == Attribute.DataType.DATE:
            if isinstance(raw, datetime.date):
                self.value_date = raw
            else:
                try:
                    self.value_date = datetime.date.fromisoformat(str(raw).strip())
                except (TypeError, ValueError):
                    raise ValidationError(
                        {self.attribute.name: f"«{label}» باید تاریخ معتبر باشد (YYYY-MM-DD)."}
                    )

        elif data_type == Attribute.DataType.SELECT:
            token = str(raw).strip()
            valid = set(
                self.attribute.options.filter(is_active=True).values_list("value", flat=True)
            )
            if token not in valid:
                raise ValidationError(
                    {self.attribute.name: f"مقدار انتخاب‌شده برای «{label}» معتبر نیست."}
                )
            self.value_text = token

        elif data_type == Attribute.DataType.MULTISELECT:
            tokens = raw if isinstance(raw, (list, tuple)) else [raw]
            tokens = [str(t).strip() for t in tokens if str(t).strip()]
            valid = set(
                self.attribute.options.filter(is_active=True).values_list("value", flat=True)
            )
            invalid = [t for t in tokens if t not in valid]
            if invalid:
                raise ValidationError(
                    {self.attribute.name: f"مقادیر نامعتبر برای «{label}»: {'، '.join(invalid)}"}
                )
            self.value_json = tokens

        else:  # pragma: no cover — guards against a new unhandled data type
            raise ValidationError(
                {self.attribute.name: f"نوع دادهٔ «{data_type}» پشتیبانی نمی‌شود."}
            )

    @property
    def display_value(self) -> str:
        """Human-readable rendering, resolving option keys to their labels."""
        from apps.basics.models import Attribute

        value = self.value
        if value is None:
            return ""

        data_type = self.attribute.data_type

        if data_type == Attribute.DataType.BOOLEAN:
            return "بله" if value else "خیر"

        if data_type == Attribute.DataType.SELECT:
            option = self.attribute.options.filter(value=value).first()
            return option.display_name if option else str(value)

        if data_type == Attribute.DataType.MULTISELECT:
            labels = dict(
                self.attribute.options.values_list("value", "display_name")
            )
            return "، ".join(labels.get(v, v) for v in (value or []))

        return str(value)

    def clean(self):
        super().clean()
        if self.attribute_id and self.attribute.is_core:
            raise ValidationError(
                "ویژگی‌های ثابت در ستون اختصاصی خود ذخیره می‌شوند، نه در جدول ویژگی‌های پویا."
            )

    def __str__(self):
        return f"{self.attribute.display_name}: {self.display_value}"
