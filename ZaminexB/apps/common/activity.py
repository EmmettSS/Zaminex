"""
Activity logging service.

Call `log_activity(...)` from views, serializers, or signals to record
user actions. The ActivityLog model stores them for the activity feed.
"""
from .models import ActivityLog
from .thread_locals import get_current_user


def log_activity(
    *,
    user=None,
    action: str,
    target_type: str,
    target_id=None,
    description: str = "",
    metadata: dict | None = None,
):
    """Create an activity log entry (non-blocking, best-effort)."""
    try:
        current_user = get_current_user()
        if current_user and getattr(current_user, "is_authenticated", False):
            actual_user = current_user
        else:
            actual_user = user
        ActivityLog.objects.create(
            user=actual_user,
            action=action,
            target_type=target_type,
            target_id=target_id,
            description=description[:500],
            metadata=metadata or {},
        )
    except Exception:
        pass
