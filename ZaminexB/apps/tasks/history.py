"""Task change-history helpers.

ActivityLog already records task events. These helpers:
  - produce precise Persian titles and field-level metadata when logging
  - serialize those logs for the task history API
"""
from __future__ import annotations

from django.contrib.auth import get_user_model

from apps.common.models import ActivityLog


STATUS_FA = {
    "PENDING": "در انتظار انجام",
    "IN_PROGRESS": "در حال انجام",
    "COMPLETED": "تکمیل‌شده",
    "CANCELLED": "لغوشده",
}

PRIORITY_FA = {
    "LOW": "اولویت کم",
    "MEDIUM": "اولویت عادی",
    "HIGH": "اولویت بالا",
    "URGENT": "اولویت فوری",
}

TYPE_FA = {
    "VIEWING": "بازدید ملک",
    "DOCUMENT": "بررسی مدارک",
    "NEGOTIATION": "مذاکره و نشست",
    "FOLLOW_UP": "پیگیری مستمر",
    "ADMINISTRATIVE": "امور اداری و دفتری",
    "SITE_VISIT": "کارشناسی میدانی",
    "CONTRACT": "عقد قرارداد",
    "INSPECTION": "بازرسی فنی",
}

ACTION_TITLES = {
    ActivityLog.ActionType.CREATE: "ایجاد وظیفه",
    ActivityLog.ActionType.UPDATE: "ویرایش وظیفه",
    ActivityLog.ActionType.DELETE: "حذف وظیفه",
    ActivityLog.ActionType.COMPLETE: "تکمیل وظیفه",
    ActivityLog.ActionType.ARCHIVE: "لغو وظیفه",
    ActivityLog.ActionType.STATUS_CHANGE: "تغییر وضعیت",
}

FIELD_TITLES = {
    "status": "تغییر وضعیت",
    "priority": "تغییر اولویت",
    "title": "تغییر عنوان",
    "description": "ویرایش توضیحات",
    "note": "افزودن/ویرایش یادداشت",
    "due_date": "تغییر سررسید",
    "assigned_to_id": "تغییر مسئول",
    "property_id": "تغییر ملک مرتبط",
    "task_type": "تغییر نوع وظیفه",
}

TRACKED_FIELDS = (
    "status",
    "priority",
    "title",
    "description",
    "note",
    "due_date",
    "assigned_to_id",
    "property_id",
    "task_type",
)


def user_display_name(user) -> str:
    if not user:
        return "سیستم"
    name = (user.get_full_name() or "").strip()
    return name or user.username or "سیستم"


def _assignee_label(user_id) -> str:
    if not user_id:
        return "—"
    User = get_user_model()
    try:
        return user_display_name(User.objects.get(pk=user_id))
    except User.DoesNotExist:
        return "—"


def _property_label(property_id) -> str:
    if not property_id:
        return "—"
    from apps.properties.models import Property

    try:
        prop = Property.objects.only("title", "internal_code").get(pk=property_id)
    except Property.DoesNotExist:
        return "—"
    return (prop.title or "").strip() or prop.internal_code or "—"


def _format_value(field: str, value) -> str:
    if value in (None, ""):
        return "—"
    if field == "status":
        return STATUS_FA.get(str(value), str(value))
    if field == "priority":
        return PRIORITY_FA.get(str(value), str(value))
    if field == "task_type":
        return TYPE_FA.get(str(value), str(value))
    if field == "assigned_to_id":
        return _assignee_label(value)
    if field == "property_id":
        return _property_label(value)
    if field == "due_date":
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    if field == "description":
        text = str(value).strip()
        if not text:
            return "—"
        return text if len(text) <= 80 else text[:77] + "…"
    if field == "note":
        text = str(value).strip()
        if not text:
            return "—"
        # Notes are free-form text; keep a compact preview in the activity log
        # so the actual content is not dumped in full into every feed row.
        return text if len(text) <= 80 else text[:77] + "…"
    return str(value)


def snapshot_task(task) -> dict:
    return {
        "status": task.status,
        "priority": task.priority,
        "title": task.title,
        "description": task.description or "",
        "note": getattr(task, "note", "") or "",
        "due_date": task.due_date,
        "assigned_to_id": task.assigned_to_id,
        "property_id": task.property_id,
        "task_type": task.task_type,
    }


def diff_task(old: dict, new: dict) -> list[dict]:
    changes = []
    for field in TRACKED_FIELDS:
        before = old.get(field)
        after = new.get(field)
        if before != after:
            changes.append(
                {
                    "field": field,
                    "from": None if before in (None, "") else str(before),
                    "to": None if after in (None, "") else str(after),
                    "fromLabel": _format_value(field, before),
                    "toLabel": _format_value(field, after),
                }
            )
    return changes


def classify_task_event(changes: list[dict]) -> tuple[str, str]:
    """Return (action, event_title) for a set of field changes."""
    fields = {c["field"] for c in changes}
    if fields == {"status"}:
        new_status = next(c["to"] for c in changes if c["field"] == "status")
        if new_status == "COMPLETED":
            return ActivityLog.ActionType.COMPLETE, "تکمیل وظیفه"
        if new_status == "CANCELLED":
            return ActivityLog.ActionType.ARCHIVE, "لغو وظیفه"
        return ActivityLog.ActionType.STATUS_CHANGE, "تغییر وضعیت"
    if len(changes) == 1:
        field = changes[0]["field"]
        return ActivityLog.ActionType.UPDATE, FIELD_TITLES.get(field, "ویرایش وظیفه")
    if "status" in fields:
        new_status = next(c["to"] for c in changes if c["field"] == "status")
        if new_status == "COMPLETED":
            return ActivityLog.ActionType.COMPLETE, "تکمیل و ویرایش وظیفه"
        if new_status == "CANCELLED":
            return ActivityLog.ActionType.ARCHIVE, "لغو و ویرایش وظیفه"
        return ActivityLog.ActionType.STATUS_CHANGE, "ویرایش وظیفه"
    return ActivityLog.ActionType.UPDATE, "ویرایش وظیفه"


def build_description(task_title: str, action: str, event_title: str, changes: list[dict]) -> str:
    quoted = f"«{task_title}»"
    if action == ActivityLog.ActionType.CREATE:
        return f"وظیفه {quoted} ایجاد شد"
    if action == ActivityLog.ActionType.COMPLETE and len(changes) <= 1:
        return f"وظیفه {quoted} تکمیل شد"
    if action == ActivityLog.ActionType.ARCHIVE and len(changes) <= 1:
        return f"وظیفه {quoted} لغو شد"
    if len(changes) == 1:
        change = changes[0]
        return (
            f"{event_title} وظیفه {quoted} "
            f"از «{change['fromLabel']}» به «{change['toLabel']}»"
        )
    labels = "، ".join(FIELD_TITLES.get(c["field"], c["field"]) for c in changes)
    return f"{event_title} {quoted}: {labels}"


def serialize_task_history_log(log: ActivityLog) -> dict:
    meta = log.metadata or {}
    changes = meta.get("changes") or []
    title = meta.get("event_title") or ACTION_TITLES.get(log.action, log.get_action_display())
    primary = changes[0] if len(changes) == 1 else None
    user_name = user_display_name(log.user)
    return {
        "id": log.id,
        "action": log.action,
        "actionLabel": log.get_action_display(),
        "title": title,
        "description": log.description,
        "from": (primary or {}).get("fromLabel"),
        "to": (primary or {}).get("toLabel"),
        "user": user_name,
        "userName": user_name,
        "createdAt": log.created_at.isoformat() if log.created_at else None,
        "changes": changes,
    }


def synthetic_create_entry(task) -> dict:
    created_at = task.created_at.isoformat() if task.created_at else None
    user_name = user_display_name(task.created_by)
    return {
        "id": f"create-{task.pk}",
        "action": ActivityLog.ActionType.CREATE,
        "actionLabel": "ایجاد",
        "title": "ایجاد وظیفه",
        "description": f"وظیفه «{task.title}» ایجاد شد",
        "from": None,
        "to": None,
        "user": user_name,
        "userName": user_name,
        "createdAt": created_at,
        "changes": [],
    }


def task_history_items(task) -> list[dict]:
    logs = (
        ActivityLog.objects.filter(
            target_type=ActivityLog.TargetType.TASK,
            target_id=task.pk,
        )
        .select_related("user")
        .order_by("-created_at", "-id")
    )
    items = [serialize_task_history_log(log) for log in logs]
    if not any(item.get("action") == ActivityLog.ActionType.CREATE for item in items):
        items.append(synthetic_create_entry(task))
    return items
