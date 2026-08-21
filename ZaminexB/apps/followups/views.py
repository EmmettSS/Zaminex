from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.pagination import LargeListPagination

from .models import FollowUp, FollowUpStatus
from .serializers import (
    FollowUpArchiveSerializer,
    FollowUpListSerializer,
    FollowUpWriteSerializer,
)


class FollowUpViewSet(viewsets.ModelViewSet):
    # Ordering: newest *activity* first. A follow-up that was created or
    # edited most recently surfaces at the top of the list and of the
    # dashboard "پیگیری‌های پیش‌رو" widget (which slices the first few rows),
    # so the order updates dynamically after every create/update/complete.
    # ``-created_at`` is the deterministic tie-breaker for records changed in
    # the same instant.
    queryset = FollowUp.objects.select_related("consultant", "property").all().order_by("-updated_at", "-created_at")
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = LargeListPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "title",
        "contact_name",
        "consultant__username",
        "consultant_name",
        "property__title",
        "property_title",
        "notes",
        "outcome",
    ]
    ordering_fields = ["scheduled_at", "created_at", "updated_at", "probability"]
    ordering = ["-updated_at", "-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if getattr(user, "role", "") != "ADMIN":
            queryset = queryset.filter(consultant=user)

        archived = self.request.query_params.get("archived")
        consultant_id = self.request.query_params.get("consultantId")
        property_id = self.request.query_params.get("propertyId")
        status_value = self.request.query_params.get("status")
        type_value = self.request.query_params.get("type")

        # The archived/active split applies to list responses only. Applying it
        # to detail routes as well would make an archived follow-up unreachable
        # by its own id, so it could never be unarchived or deleted.
        if self.action == "list":
            if archived in ("true", "1", "yes"):
                queryset = queryset.filter(is_archived=True)
            elif archived in ("false", "0", "no", None):
                queryset = queryset.filter(is_archived=False)

        if consultant_id:
            queryset = queryset.filter(consultant_id=consultant_id)

        if property_id:
            queryset = queryset.filter(property_id=property_id)

        if status_value:
            queryset = queryset.filter(status=status_value)

        if type_value:
            queryset = queryset.filter(follow_up_type=type_value)

        return queryset

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return FollowUpListSerializer
        if self.action in {"archive", "unarchive"}:
            return FollowUpArchiveSerializer
        return FollowUpWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = FollowUpListSerializer(instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = FollowUpListSerializer(instance, context=self.get_serializer_context())
        return Response(output.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        instance = self.get_object()
        instance.archive()
        serializer = FollowUpArchiveSerializer({"is_archived": instance.is_archived})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        instance = self.get_object()
        instance.unarchive()
        serializer = FollowUpArchiveSerializer({"is_archived": instance.is_archived})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="my-followups")
    def my_followups(self, request):
        consultant_id = request.query_params.get("consultantId")
        if not consultant_id:
            return Response(
                {"detail": "پارامتر consultantId الزامی است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(
            consultant_id=consultant_id,
            is_archived=False,
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = FollowUpListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = FollowUpListSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        queryset = self.get_queryset().filter(is_archived=False)
        payload = {
            "total": queryset.count(),
            "scheduled": queryset.filter(status=FollowUpStatus.SCHEDULED).count(),
            "completed": queryset.filter(status=FollowUpStatus.COMPLETED).count(),
        }
        return Response(payload, status=status.HTTP_200_OK)
