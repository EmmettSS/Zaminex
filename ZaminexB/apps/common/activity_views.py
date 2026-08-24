"""Activity log API views."""
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole

from .models import ActivityLog

User = get_user_model()

# Only these roles get a Persian display label in the "filter by user" list;
# any unknown role falls back to its raw value rather than a wrong label.
_ROLE_LABELS = {UserRole.ADMIN: "مدیر", UserRole.AGENT: "مشاور"}


def _is_admin(request) -> bool:
    return getattr(request.user, "role", "") == UserRole.ADMIN


class ActivityLogPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


class ActivityLogListView(APIView):
    """
    GET /common/api/activity-log/
    Query params:
      - action: filter by action type (create, update, delete, ...)
      - target_type: filter by target (property, listing, task, ...)
      - user_id: filter by the user who performed the action. Accepts a
        user primary key or "system" for system-generated entries
        (user is null). Only honoured for admins — every other role is
        always scoped to its own entries, so the parameter can never
        widen (or change) what they are allowed to see.
      - days: number of days to look back (default 30)
      - page_size: items per page (default 30)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = ActivityLog.objects.select_related("user").all()
        admin = _is_admin(request)

        action = request.query_params.get("action")
        if action and action != "all":
            qs = qs.filter(action=action)

        target_type = request.query_params.get("target_type")
        if target_type and target_type != "all":
            qs = qs.filter(target_type=target_type)

        user_id = request.query_params.get("user_id")
        if admin and user_id and user_id != "all":
            if user_id == "system":
                qs = qs.filter(user__isnull=True)
            elif user_id.isdigit() and int(user_id) > 0:
                qs = qs.filter(user_id=int(user_id))

        if not admin:
            qs = qs.filter(Q(user=request.user) | Q(user__isnull=True))

        days = request.query_params.get("days")
        if days:
            try:
                days_int = int(days)
                since = timezone.now() - timedelta(days=days_int)
                qs = qs.filter(created_at__gte=since)
            except (ValueError, TypeError):
                pass

        now = timezone.now()
        week_ago = now - timedelta(days=7)

        total_count = qs.count()
        this_week_count = qs.filter(created_at__gte=week_ago).count()
        completed_count = qs.filter(action=ActivityLog.ActionType.COMPLETE).count()

        paginator = ActivityLogPagination()
        page = paginator.paginate_queryset(qs, request)

        items = []
        for log in page:
            if log.user is None:
                user_name = "سیستم"
                user_avatar = "سی"
            else:
                user_name = log.user.get_full_name() or log.user.username
                user_avatar = user_name[:2].upper()
            items.append({
                "id": log.id,
                "userId": log.user_id,
                "userName": user_name,
                "userAvatar": user_avatar,
                "action": log.action,
                "actionLabel": log.get_action_display(),
                "targetType": log.target_type,
                "targetTypeLabel": log.get_target_type_display(),
                "targetId": log.target_id,
                "description": log.description,
                "metadata": log.metadata,
                "createdAt": log.created_at.isoformat(),
            })

        response_data = paginator.get_paginated_response(items).data
        response_data["summary"] = {
            "total": total_count,
            "thisWeek": this_week_count,
            "completed": completed_count,
        }
        return Response(response_data)

    def delete(self, request):
        """
        DELETE /common/api/activity-log/
        Admin-only endpoint to clear all activity log entries.
        """
        if getattr(request.user, "role", "") != "ADMIN":
            return Response(
                {"detail": "فقط مدیران سیستم می‌توانند تمامی گزارش‌های فعالیت را حذف کنند."},
                status=403,
            )

        deleted_count, _ = ActivityLog.objects.all().delete()
        return Response(
            {
                "detail": "تمامی گزارش‌های فعالیت با موفقیت حذف شدند.",
                "deleted": deleted_count,
            },
            status=200,
        )


class ActivityLogUserListView(APIView):
    """
    GET /common/api/activity-log/users/
    Admin-only. Lists every user that appears in the activity log with a
    per-user entry count, plus the count of system entries (user is null).
    Feeds the "filter by user" control on the activity report page.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_admin(request):
            return Response(
                {"detail": "فقط مدیران به این بخش دسترسی دارند."},
                status=403,
            )

        rows = (
            ActivityLog.objects.values("user_id")
            .annotate(log_count=Count("id"))
        )
        log_counts: dict[int, int] = {}
        system_count = 0
        for row in rows:
            if row["user_id"] is None:
                system_count = row["log_count"]
            else:
                log_counts[row["user_id"]] = row["log_count"]

        users = [
            {
                "id": user.id,
                # Same name rule as the log rows themselves, so a filter
                # entry always matches the name shown in the feed.
                "name": user.get_full_name() or user.username,
                "role": user.role,
                "roleLabel": _ROLE_LABELS.get(user.role, user.role),
                "logCount": log_counts[user.id],
            }
            for user in User.objects.filter(pk__in=log_counts)
        ]
        users.sort(key=lambda item: (-item["logCount"], item["name"]))

        return Response({"users": users, "systemCount": system_count})
