from django.db.models import Q
from django.utils import timezone

from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.thread_locals import set_current_user

from .history import task_history_items
from .models import Task
from .serializers import TaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "title",
        "description",
        "assigned_to__username",
        "assigned_to__first_name",
        "assigned_to__last_name",
        "created_by__username",
        "property__title",
        "property__internal_code",
    ]
    ordering_fields = ["due_date", "created_at", "updated_at", "priority", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Task.objects.none()

        qs = Task.objects.select_related(
            "assigned_to",
            "created_by",
            "property",
        ).all()

        if getattr(user, "role", "") != "ADMIN":
            qs = qs.filter(Q(assigned_to=user) | Q(created_by=user))

        scope = self.request.query_params.get("scope")
        if scope == "mine":
            qs = qs.filter(assigned_to=user)
        elif scope == "created":
            qs = qs.filter(created_by=user)

        assigned_to = self.request.query_params.get("assignedTo")
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)

        property_id = self.request.query_params.get("propertyId")
        if property_id:
            qs = qs.filter(property_id=property_id)

        task_status = self.request.query_params.get("status")
        if task_status:
            qs = qs.filter(status=task_status.upper())

        priority = self.request.query_params.get("priority")
        if priority:
            qs = qs.filter(priority=priority.upper())

        task_type = self.request.query_params.get("taskType")
        if task_type:
            qs = qs.filter(task_type=task_type.upper())

        return qs

    def _bind_actor(self):
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            set_current_user(user)

    def perform_create(self, serializer):
        self._bind_actor()
        user = self.request.user
        if not serializer.validated_data.get("created_by"):
            serializer.save(created_by=user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        self._bind_actor()
        serializer.save()

    def perform_destroy(self, instance):
        self._bind_actor()
        instance.delete()

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        self._bind_actor()
        instance = self.get_object()
        instance.mark_completed()
        return Response(TaskSerializer(instance).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """Return chronological change history for a single task."""
        instance = self.get_object()
        return Response({"results": task_history_items(instance)}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        queryset = self.get_queryset()
        return Response(
            {
                "total": queryset.count(),
                "pending": queryset.filter(status="PENDING").count(),
                "in_progress": queryset.filter(status="IN_PROGRESS").count(),
                "completed": queryset.filter(status="COMPLETED").count(),
                "cancelled": queryset.filter(status="CANCELLED").count(),
                "overdue": queryset.filter(
                    due_date__lt=timezone.now().date()
                ).exclude(status="COMPLETED").count(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="types")
    def types(self, request):
        """Return list of task types with Persian labels."""
        from .models import Task as TaskModel
        
        # Persian labels for task types
        persian_labels = {
            "VIEWING": "بازدید ملک",
            "DOCUMENT": "بررسی مدارک",
            "NEGOTIATION": "مذاکره و نشست",
            "FOLLOW_UP": "پیگیری مستمر",
            "ADMINISTRATIVE": "امور اداری و دفتری",
            "SITE_VISIT": "کارشناسی میدانی",
            "CONTRACT": "عقد قرارداد",
            "INSPECTION": "بازرسی فنی",
        }
        
        task_types = []
        for choice in TaskModel.TaskType.choices:
            value = choice[0]
            task_types.append({
                "value": value,
                "label": persian_labels.get(value, choice[1]),
            })
        
        return Response(task_types, status=status.HTTP_200_OK)
