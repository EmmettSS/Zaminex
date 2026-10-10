from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models


class AttributeValueQuerySet(models.QuerySet):
    def for_attribute(self, name: str):
        return self.filter(attribute__name=name)


class BaseAttributeValue(models.Model):
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

    @property
    def value(self):
        return getattr(self, self.attribute.value_field)

    @value.setter
    def value(self, raw):
        self.set_value(raw)

    def set_value(self, raw):
        from apps.basics.models import Attribute

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
            if (
                self.attribute.input_type == Attribute.InputType.PRICE
                or "تومان" in (self.attribute.unit or "")
            ) and self.value_integer <= 0:
                raise ValidationError({self.attribute.name: f"«{label}» باید بیشتر از صفر باشد."})

        elif data_type == Attribute.DataType.DECIMAL:
            try:
                self.value_decimal = Decimal(str(raw).strip().replace(",", ""))
            except (TypeError, ValueError, InvalidOperation):
                raise ValidationError({self.attribute.name: f"«{label}» باید عدد باشد."})
            if (
                self.attribute.input_type == Attribute.InputType.PRICE
                or "تومان" in (self.attribute.unit or "")
            ) and self.value_decimal <= 0:
                raise ValidationError({self.attribute.name: f"«{label}» باید بیشتر از صفر باشد."})

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

        else:
            raise ValidationError(
                {self.attribute.name: f"نوع دادهٔ «{data_type}» پشتیبانی نمی‌شود."}
            )

    @property
    def display_value(self) -> str:
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
