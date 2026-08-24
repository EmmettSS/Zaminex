"""Shared helpers for inclusive calendar-date range filtering.

The API and database stay Gregorian. The UI (a Jalali date picker) converts
the user's selection to Gregorian ``YYYY-MM-DD`` strings before sending them,
so these helpers only ever deal with Gregorian dates.

Two model shapes are supported:

* A plain ``DateField`` (e.g. ``Task.due_date``) — compared directly with
  ``__gte`` / ``__lte``, which the database can evaluate against the existing
  index on the column.
* A timezone-aware ``DateTimeField`` (e.g. ``FollowUp.scheduled_at``) — the
  selected Gregorian day must be interpreted in the project's business
  timezone (``Asia/Tehran``). A naive ``.filter(scheduled_at__date=...)`` or
  slicing the serialized string at character 10 uses the *UTC* calendar day
  and therefore drops records scheduled in the first hours after Tehran
  midnight. We instead convert each endpoint to an explicit, timezone-aware
  half-open interval ``[start, end_exclusive)`` expressed in UTC, which is
  unambiguous, index-friendly and DST-correct.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.utils.dateparse import parse_date
from rest_framework.serializers import ValidationError as DRFValidationError

# Strict YYYY-MM-DD (Gregorian). The Jalali picker always sends this shape;
# anything else is a malformed/hand-crafted request and is rejected as 400.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Project business timezone. The database stores UTC (USE_TZ=True,
# TIME_ZONE='UTC'), but "which calendar day does this follow-up belong to?"
# is answered in Tehran local time — the same clock the UI and the users use.
BUSINESS_TZ = ZoneInfo("Asia/Tehran")


def parse_gregorian_date(value: str | None, field: str) -> datetime.date | None:
    """Parse a ``YYYY-MM-DD`` query parameter into a date, or raise a
    structured Persian 400 when it is missing/invalid.

    ``field`` is the public query-parameter name and is echoed back in the
    error payload so the frontend can associate the message with the right
    input.
    """
    if value is None or value == "":
        return None
    text = str(value)
    # Reject anything that is not exactly YYYY-MM-DD up front. parse_date()
    # is lenient about separators and, more importantly, can raise ValueError
    # (rather than returning None) for out-of-range months/days.
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
    """Reject a range where the start is after the end.

    Returning an empty list silently would be confusing; a 400 lets the UI
    show a clear Persian validation message and not apply the filter.
    """
    if date_from and date_to and date_from > date_to:
        raise DRFValidationError(
            {
                field_from: "تاریخ شروع نمی‌تواند پس از تاریخ پایان باشد.",
                field_to: "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد.",
            }
        )


def apply_date_field_range(queryset, field_name: str, date_from, date_to):
    """Inclusive ``[date_from, date_to]`` filter on a ``DateField``."""
    if date_from is not None:
        queryset = queryset.filter(**{f"{field_name}__gte": date_from})
    if date_to is not None:
        queryset = queryset.filter(**{f"{field_name}__lte": date_to})
    return queryset


def _tehran_day_bounds(day):
    """Return the UTC ``[start, end_exclusive)`` timestamps covering one
    Tehran calendar date."""
    start_local = datetime.combine(day, time.min, tzinfo=BUSINESS_TZ)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(dt_timezone.utc), end_local.astimezone(
        dt_timezone.utc
    )


def apply_datetime_field_range(queryset, field_name: str, date_from, date_to):
    """Inclusive Tehran-calendar-day range on a timezone-aware ``DateTimeField``.

    ``date_from`` includes every instant of that Tehran day (from 00:00 Tehran
    onward); ``date_to`` includes the whole of that Tehran day (up to but not
    including the next Tehran midnight). The bounds are converted to UTC so
    the comparison uses the same absolute instants regardless of the server's
    ``TIME_ZONE``.
    """
    if date_from is not None:
        start_utc, _ = _tehran_day_bounds(date_from)
        queryset = queryset.filter(**{f"{field_name}__gte": start_utc})
    if date_to is not None:
        _, end_exclusive_utc = _tehran_day_bounds(date_to)
        queryset = queryset.filter(**{f"{field_name}__lt": end_exclusive_utc})
    return queryset
