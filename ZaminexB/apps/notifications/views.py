from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

POLL_TTL = 10


def _notifications_poll_key(user) -> str:
    from apps.common import cache_utils

    return cache_utils.make_key("poll", "notifications", user.pk)


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.common import cache_utils
        from .models import Notification

        key = _notifications_poll_key(request.user)
        cached = cache_utils.cache_get(key)
        if isinstance(cached, dict):
            return Response(cached)

        notifications = Notification.objects.filter(user=request.user)[:50]

        data = []
        for notif in notifications:
            data.append({
                "id": notif.id,
                "type": notif.type,
                "typeLabel": notif.get_type_display(),
                "title": notif.title,
                "message": notif.message,
                "isRead": notif.is_read,
                "createdAt": notif.created_at.isoformat(),
                "metadata": notif.metadata,
            })

        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

        payload = {
            "notifications": data,
            "unreadCount": unread_count,
        }
        cache_utils.cache_set(key, payload, POLL_TTL)
        return Response(payload)


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        from apps.common import cache_utils
        from .models import Notification

        try:
            notif = Notification.objects.get(pk=pk, user=request.user)
            notif.is_read = True
            notif.save()
            cache_utils.cache_delete(_notifications_poll_key(request.user))
            return Response({"success": True})
        except Notification.DoesNotExist:
            return Response({"error": "اعلان یافت نشد"}, status=404)
