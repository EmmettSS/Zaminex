from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.utils.dateparse import parse_date
from rest_framework.serializers import ValidationError as DRFValidationError

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

BUSINESS_TZ = ZoneInfo("Asia/Tehran")


def parse_gregorian_date(value: str | None, field: str) -> datetime.date | None:
    if value is None or value == "":
        return None
    text = str(value)
    if not _ISO_DATE_RE.match(text):
        raise DRFValidationError(
            {field: "تاریخ باید به فرمت میلادی YYYY-MM-DD (مثلاً 2026-07-18) باشد."}
        )
    try:
        parsed = parse_date(text)
    except ValueError:
        parsed = None
    if parsed is None:
        raise DRFValidationError(
            {field: "تاریخ باید به فرمت میلادی YYYY-MM-DD (مثلاً 2026-07-18) باشد."}
        )
    return parsed


def validate_date_range(
    date_from: datetime.date | None,
    date_to: datetime.date | None,
    field_from: str,
    field_to: str,
) -> None:
    if date_from and date_to and date_from > date_to:
        raise DRFValidationError(
            {
                field_from: "تاریخ شروع نمی‌تواند پس از تاریخ پایان باشد.",
                field_to: "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد.",
            }
        )


def apply_date_field_range(queryset, field_name: str, date_from, date_to):
    if date_from is not None:
        queryset = queryset.filter(**{f"{field_name}__gte": date_from})
    if date_to is not None:
        queryset = queryset.filter(**{f"{field_name}__lte": date_to})
    return queryset


def _tehran_day_bounds(day):
    start_local = datetime.combine(day, time.min, tzinfo=BUSINESS_TZ)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(dt_timezone.utc), end_local.astimezone(
        dt_timezone.utc
    )


def apply_datetime_field_range(queryset, field_name: str, date_from, date_to):
    if date_from is not None:
        start_utc, _ = _tehran_day_bounds(date_from)
        queryset = queryset.filter(**{f"{field_name}__gte": start_utc})
    if date_to is not None:
        _, end_exclusive_utc = _tehran_day_bounds(date_to)
        queryset = queryset.filter(**{f"{field_name}__lt": end_exclusive_utc})
    return queryset
