from __future__ import annotations

import re

from apps.followups.models import FollowUpStatus, FollowUpType
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task

_PROPERTY_STATUS_FA = {
    "AVAILABLE": "آماده واگذاری",
    "RESERVED": "رزرو شده",
    "SOLD": "فروخته/واگذارشده",
    "INACTIVE": "بایگانی‌شده",
}

_LISTING_STATUS_FA = {
    "DRAFT": "پیش‌نویس",
    "ACTIVE": "منتشرشده (فعال)",
    "PAUSED": "متوقف‌شده",
    "SOLD": "فروخته‌شده",
    "EXPIRED": "منقضی‌شده",
    "ARCHIVED": "بایگانی‌شده",
}

_TASK_STATUS_FA = {
    "PENDING": "در انتظار انجام",
    "IN_PROGRESS": "در حال انجام",
    "COMPLETED": "تکمیل‌شده",
    "CANCELLED": "لغوشده",
}

_TASK_PRIORITY_FA = {
    "LOW": "اولویت کم",
    "MEDIUM": "اولویت عادی",
    "HIGH": "اولویت بالا",
    "URGENT": "اولویت فوری",
}

_TASK_TYPE_FA = {
    "VIEWING": "بازدید ملک",
    "DOCUMENT": "بررسی مدارک",
    "NEGOTIATION": "مذاکره و نشست",
    "FOLLOW_UP": "پیگیری مستمر",
    "ADMINISTRATIVE": "امور اداری و دفتری",
    "SITE_VISIT": "کارشناسی میدانی",
    "CONTRACT": "عقد قرارداد",
    "INSPECTION": "بازرسی فنی",
}

_FOLLOWUP_TYPE_FA = {
    "Call": "تماس تلفنی",
    "Meeting": "جلسه حضوری",
    "Email": "ارسال پیام/ایمیل",
    "Site Visit": "بازدید میدانی ملک",
}

_FOLLOWUP_STATUS_FA = {
    "scheduled": "برنامه‌ریزی‌شده",
    "completed": "تکمیل‌شده",
}


def _choice_tokens(choices_cls, fa_map: dict[str, str], legacy_en: dict[str, str]) -> dict[str, str]:
    tokens: dict[str, str] = dict(legacy_en)
    for code, label in choices_cls.choices:
        fa = fa_map.get(code)
        if fa is None:
            continue
        tokens[code] = fa
        tokens[label] = fa
    return tokens


_LEGACY_EN: dict[str, dict[str, str]] = {
    "property": {
        "Available": "آماده واگذاری",
        "Reserved": "رزرو شده",
        "Sold": "فروخته/واگذارشده",
        "Archived": "بایگانی‌شده",
    },
    "listing": {
        "Draft": "پیش‌نویس",
        "Active": "منتشرشده (فعال)",
        "Paused": "متوقف‌شده",
        "Sold": "فروخته‌شده",
        "Expired": "منقضی‌شده",
        "Archived": "بایگانی‌شده",
    },
    "task": {
        "Pending": "در انتظار انجام",
        "In Progress": "در حال انجام",
        "Completed": "تکمیل‌شده",
        "Cancelled": "لغوشده",
        "Low": "اولویت کم",
        "Medium": "اولویت عادی",
        "High": "اولویت بالا",
        "Urgent": "اولویت فوری",
        "Viewing": "بازدید ملک",
        "Document": "بررسی مدارک",
        "Negotiation": "مذاکره و نشست",
        "Follow-Up": "پیگیری مستمر",
        "Administrative": "امور اداری و دفتری",
        "Site Visit": "کارشناسی میدانی",
        "Contract": "عقد قرارداد",
        "Inspection": "بازرسی فنی",
    },
    "followup": {
        "Call": "تماس تلفنی",
        "Meeting": "جلسه حضوری",
        "Email": "ارسال پیام/ایمیل",
        "Site Visit": "بازدید میدانی ملک",
        "Scheduled": "برنامه‌ریزی‌شده",
        "Completed": "تکمیل‌شده",
    },
}


_TARGET_TOKENS: dict[str, dict[str, str]] = {
    "property": _choice_tokens(Property.Status, _PROPERTY_STATUS_FA, _LEGACY_EN["property"]),
    "listing": _choice_tokens(Listing.Status, _LISTING_STATUS_FA, _LEGACY_EN["listing"]),
    "task": {
        **_choice_tokens(Task.Status, _TASK_STATUS_FA, _LEGACY_EN["task"]),
        **_choice_tokens(Task.Priority, _TASK_PRIORITY_FA, _LEGACY_EN["task"]),
        **_choice_tokens(Task.TaskType, _TASK_TYPE_FA, _LEGACY_EN["task"]),
    },
    "followup": {
        **_choice_tokens(FollowUpType, _FOLLOWUP_TYPE_FA, _LEGACY_EN["followup"]),
        **_choice_tokens(FollowUpStatus, _FOLLOWUP_STATUS_FA, _LEGACY_EN["followup"]),
    },
}


def status_label(target_type: str, code) -> str:
    tokens = _TARGET_TOKENS.get(target_type, {})
    return tokens.get(code, code if code is not None else "")


def translate_description(description: str, target_type: str) -> str:
    if not description:
        return description
    tokens = _TARGET_TOKENS.get(target_type)
    if not tokens:
        return description
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True)) + r")\b"
    )
    return pattern.sub(lambda m: tokens[m.group(1)], description)
