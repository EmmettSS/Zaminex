from __future__ import annotations

import datetime
from typing import Any

from apps.common import cache_utils

from .services import compute_consultant_scope_report, compute_property_report

PROPERTY_REPORT_TTL = 120
SCOPE_REPORT_TTL = 60

_REPORT_LOCK_TIMEOUT = 10
_REPORT_LOCK_WAIT = 2


def _range_tag(filters: dict | None) -> str:
    filters = filters or {}
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    return (
        f"{date_from.isoformat() if date_from is not None else ''}"
        f"|{date_to.isoformat() if date_to is not None else ''}"
    )


def _json_stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json_stable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_stable(v) for v in value]
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def cached_property_report(prop, *, filters: dict | None = None) -> dict[str, Any]:
    key = cache_utils.make_key("report", "property", prop.pk)
    tag = _range_tag(filters)
    lock_key = key + ":lock"
    with cache_utils.with_lock(
        lock_key, timeout=_REPORT_LOCK_TIMEOUT, wait=_REPORT_LOCK_WAIT
    ):
        entries = cache_utils.cache_get(key)
        if not isinstance(entries, dict):
            entries = {}
        entry = entries.get(tag)
        if isinstance(entry, dict):
            return entry

        report = _json_stable(compute_property_report(prop, filters=filters))
        entries[tag] = report
        cache_utils.cache_set(key, entries, PROPERTY_REPORT_TTL)
        return report


def cached_consultant_scope_report(user) -> dict[str, Any]:
    key = cache_utils.make_key("report", "consultant", user.pk)

    def compute():
        return compute_consultant_scope_report(user)

    return cache_utils.cache_or_compute(key, compute, SCOPE_REPORT_TTL)
