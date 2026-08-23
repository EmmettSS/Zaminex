"""API endpoints for ticket lists, conversations and protected files."""

from __future__ import annotations

import csv
import io
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import filters, permissions, status, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.activity import log_activity
from apps.common.date_filters import (
    apply_datetime_field_range,
    parse_gregorian_date,
    validate_date_range,
)
from apps.common.pagination import StandardResultsSetPagination

from .access import (
    active_recipient_queryset,
    can_view_ticket,
    subject_queryset_for_user,
    visible_ticket_queryset,
)
from .models import (
    TicketMessage,
    TicketParticipantRole,
    TicketPriority,
    TicketStatus,
    TicketSubject,
    TicketType,
)
from .serializers import (
    TicketAuditSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
    TicketRecipientSerializer,
    TicketReplySerializer,
    TicketUpdateSerializer,
    user_display_name,
)
from .services import (
    add_message,
    close_ticket,
    create_ticket,
    mark_read,
    reopen_ticket,
    update_ticket_metadata,
)


User = get_user_model()


class TicketViewSet(viewsets.ModelViewSet):
    """Role-scoped CRUD facade for the ticket workspace."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        "created_at",
        "updated_at",
        "last_message_at",
        "sla_due_at",
        "priority",
        "status",
    ]
    ordering = ["-updated_at", "-id"]

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        if self.action == "retrieve":
            return TicketDetailSerializer
        if self.action == "reply":
            return TicketReplySerializer
        if self.action in {"update", "partial_update"}:
            return TicketUpdateSerializer
        return TicketListSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = visible_ticket_queryset(user)

        # Folders and filters are list-only. Detail/reply/action routes must
        # never become 404 merely because a stale list filter is present.
        if getattr(self, "action", None) not in {"list", "export"}:
            return queryset

        folder = (self.request.query_params.get("folder") or "received").lower()
        if folder == "sent":
            queryset = queryset.filter(created_by_id=user.pk)
        elif folder == "received":
            queryset = queryset.filter(
                participants__user_id=user.pk,
                participants__role=TicketParticipantRole.RECIPIENT,
            )
        elif folder == "all":
            if getattr(user, "role", "") != "ADMIN":
                # Non-admin callers can still use all for convenience, but it
                # remains the already-scoped sent + received universe.
                queryset = queryset.filter(
                    Q(created_by_id=user.pk)
                    | Q(
                        participants__user_id=user.pk,
                        participants__role=TicketParticipantRole.RECIPIENT,
                    )
                )
        else:
            raise serializers.ValidationError({"folder": "پوشه تیکت معتبر نیست."})

        status_value = self.request.query_params.get("status")
        ticket_type = self.request.query_params.get(
            "ticketType"
        ) or self.request.query_params.get("ticket_type")
        subject_type = self.request.query_params.get(
            "subjectType"
        ) or self.request.query_params.get("subject_type")
        priority = self.request.query_params.get("priority")
        if status_value and status_value.lower() != "all":
            normalized_status = status_value.upper()
            if normalized_status in {TicketStatus.ANSWERED, TicketStatus.WAITING_REPLY}:
                queryset = queryset.filter(
                    self._visible_reply_count_q(
                        user, positive=normalized_status == TicketStatus.ANSWERED
                    )
                )
                if normalized_status == TicketStatus.WAITING_REPLY:
                    queryset = queryset.exclude(status=TicketStatus.CLOSED)
            else:
                queryset = queryset.filter(status=normalized_status)
        if ticket_type and ticket_type.lower() != "all":
            queryset = queryset.filter(ticket_type=ticket_type.upper())
        if subject_type and subject_type.lower() != "all":
            queryset = queryset.filter(subject_type=subject_type.upper())
        if priority and priority.lower() != "all":
            queryset = queryset.filter(priority=priority.upper())

        response_state = (self.request.query_params.get("response") or "").lower()
        if response_state in {"unanswered", "no_reply", "without_reply"}:
            queryset = queryset.filter(
                self._visible_reply_count_q(user, positive=False)
            )
        elif response_state in {"answered", "replied"}:
            queryset = queryset.filter(self._visible_reply_count_q(user, positive=True))
        elif response_state in {"waiting", "waiting_for_me", "needs_response"}:
            queryset = (
                queryset.filter(participants__user_id=user.pk)
                .exclude(
                    participants__user_id=user.pk,
                    participants__last_visible_sender_id=user.pk,
                )
                .exclude(status=TicketStatus.CLOSED)
            )

        has_reply = self.request.query_params.get(
            "hasReply"
        ) or self.request.query_params.get("has_reply")
        if str(has_reply).lower() in {"true", "1", "yes"}:
            queryset = queryset.filter(self._visible_reply_count_q(user, positive=True))
        elif str(has_reply).lower() in {"false", "0", "no"}:
            queryset = queryset.filter(
                self._visible_reply_count_q(user, positive=False)
            )

        read_state = (self.request.query_params.get("read") or "").lower()
        if read_state in {"unread", "new", "false", "0"}:
            queryset = queryset.filter(
                participants__user_id=user.pk, participants__is_read=False
            )
        elif read_state in {"read", "true", "1"}:
            queryset = queryset.filter(
                participants__user_id=user.pk, participants__is_read=True
            )

        if self.request.query_params.get("overdue") in {"true", "1", "yes"}:
            queryset = queryset.filter(sla_due_at__lt=timezone.now()).exclude(
                status=TicketStatus.CLOSED
            )

        sender_id = self.request.query_params.get(
            "senderId"
        ) or self.request.query_params.get("sender_id")
        recipient_id = self.request.query_params.get(
            "recipientId"
        ) or self.request.query_params.get("recipient_id")
        if sender_id:
            queryset = queryset.filter(created_by_id=sender_id)
        if recipient_id:
            queryset = queryset.filter(
                participants__user_id=recipient_id,
                participants__role=TicketParticipantRole.RECIPIENT,
            )

        # Admin monitoring can filter one user in either direction. The
        # consultant UI never exposes this control; the base scope still makes
        # a hand-crafted request harmless.
        user_id = self.request.query_params.get(
            "userId"
        ) or self.request.query_params.get("consultantId")
        if user_id and getattr(user, "role", "") == "ADMIN":
            queryset = queryset.filter(
                Q(created_by_id=user_id)
                | Q(
                    participants__user_id=user_id,
                    participants__role=TicketParticipantRole.RECIPIENT,
                )
            )

        subject_id = self.request.query_params.get(
            "subjectId"
        ) or self.request.query_params.get("subject_id")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        q = (self.request.query_params.get("q") or "").strip()
        if q:
            visible_message_match = Q(messages__body__icontains=q)
            visible_subject_match = (
                Q(property__title__icontains=q)
                | Q(property__internal_code__icontains=q)
                | Q(listing__title__icontains=q)
                | Q(followup__title__icontains=q)
                | Q(task__title__icontains=q)
                | Q(related_ticket__title__icontains=q)
                | Q(related_ticket__ticket_number__icontains=q)
            )
            if getattr(user, "role", "") != "ADMIN":
                # Do not let a recipient infer the contents of another
                # recipient's private branch or hidden subject through search.
                visible_message_match &= (
                    Q(created_by_id=user.pk)
                    | Q(messages__thread_recipient__isnull=True)
                    | Q(messages__thread_recipient_id=user.pk)
                )
                visible_subject_match = (
                    Q(
                        subject_type=TicketSubject.PROPERTY,
                        property__consultant_id=user.pk,
                    )
                    | Q(
                        subject_type=TicketSubject.PROPERTY,
                        property__is_shared=True,
                    )
                    | Q(
                        subject_type=TicketSubject.LISTING,
                        listing__created_by_id=user.pk,
                    )
                    | Q(
                        subject_type=TicketSubject.LISTING,
                        listing__assigned_to_id=user.pk,
                    )
                    | Q(
                        subject_type=TicketSubject.FOLLOWUP,
                        followup__consultant_id=user.pk,
                    )
                    | Q(
                        subject_type=TicketSubject.TASK,
                        task__created_by_id=user.pk,
                    )
                    | Q(
                        subject_type=TicketSubject.TASK,
                        task__assigned_to_id=user.pk,
                    )
                    | Q(
                        subject_type=TicketSubject.TICKET,
                        related_ticket__created_by_id=user.pk,
                    )
                    | Q(
                        subject_type=TicketSubject.TICKET,
                        related_ticket__participants__user_id=user.pk,
                        related_ticket__participants__role=TicketParticipantRole.RECIPIENT,
                    )
                ) & visible_subject_match
            queryset = queryset.filter(
                Q(ticket_number__icontains=q)
                | Q(title__icontains=q)
                | visible_message_match
                | Q(created_by__username__icontains=q)
                | Q(created_by__first_name__icontains=q)
                | Q(created_by__last_name__icontains=q)
                | visible_subject_match
            ).distinct()

        queryset = self._apply_date_filters(queryset)
        return queryset.distinct()

    @staticmethod
    def _visible_reply_count_q(user, *, positive: bool):
        """Build a viewer-scoped answered/unanswered predicate.

        A recipient must not be able to infer that another private branch has
        replies. Owners and admins can see the global counter; recipients use
        the denormalized per-participant counter.
        """

        if getattr(user, "role", "") == "ADMIN":
            return Q(reply_count__gt=0) if positive else Q(reply_count=0)

        if positive:
            return Q(
                created_by_id=user.pk,
                reply_count__gt=0,
            ) | Q(
                participants__user_id=user.pk,
                participants__role=TicketParticipantRole.RECIPIENT,
                visible_reply_count__gt=0,
            )
        return Q(
            created_by_id=user.pk,
            reply_count=0,
        ) | Q(
            participants__user_id=user.pk,
            participants__role=TicketParticipantRole.RECIPIENT,
            visible_reply_count=0,
        )

    def _apply_date_filters(self, queryset):
        """Apply inclusive Tehran-calendar dates to list/export queries."""

        created_from = parse_gregorian_date(
            self.request.query_params.get("createdFrom")
            or self.request.query_params.get("createdDateFrom"),
            "createdFrom",
        )
        created_to = parse_gregorian_date(
            self.request.query_params.get("createdTo")
            or self.request.query_params.get("createdDateTo"),
            "createdTo",
        )
        updated_from = parse_gregorian_date(
            self.request.query_params.get("updatedFrom")
            or self.request.query_params.get("updatedDateFrom"),
            "updatedFrom",
        )
        updated_to = parse_gregorian_date(
            self.request.query_params.get("updatedTo")
            or self.request.query_params.get("updatedDateTo"),
            "updatedTo",
        )
        validate_date_range(created_from, created_to, "createdFrom", "createdTo")
        validate_date_range(updated_from, updated_to, "updatedFrom", "updatedTo")
        queryset = apply_datetime_field_range(
            queryset, "created_at", created_from, created_to
        )
        queryset = apply_datetime_field_range(
            queryset, "updated_at", updated_from, updated_to
        )
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(
            page if page is not None else queryset, many=True
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        ticket = self.get_object()
        try:
            changed = mark_read(ticket=ticket, actor=request.user)
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        if changed:
            # The queryset's participant prefetch was built before mark_read.
            # Update its in-memory row so the response immediately says read.
            for participant in getattr(ticket, "_ticket_participants", []) or []:
                if participant.user_id == request.user.pk:
                    participant.is_read = True
                    participant.read_at = timezone.now()

        messages = (
            TicketMessage.objects.filter(ticket=ticket)
            .select_related("sender", "thread_recipient")
            .prefetch_related("attachments")
        )
        if (
            getattr(request.user, "role", "") != "ADMIN"
            and ticket.created_by_id != request.user.pk
        ):
            messages = messages.filter(
                Q(thread_recipient__isnull=True)
                | Q(thread_recipient_id=request.user.pk)
            )
        ticket._visible_messages = messages.order_by("created_at", "id")
        return Response(
            TicketDetailSerializer(ticket, context={"request": request}).data
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ticket = create_ticket(
                actor=request.user, validated_data=serializer.validated_data
            )
        except (ValueError, DjangoValidationError) as exc:
            detail = (
                getattr(exc, "message_dict", None)
                or getattr(exc, "messages", None)
                or str(exc)
            )
            raise serializers.ValidationError(detail) from exc
        output = TicketDetailSerializer(ticket, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return self._update_metadata(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self._update_metadata(request, *args, **kwargs)

    def _update_metadata(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") != "ADMIN":
            raise PermissionDenied(
                "فقط مدیران می‌توانند اطلاعات مدیریتی تیکت را ویرایش کنند."
            )
        ticket = self.get_object()
        serializer = self.get_serializer(ticket, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_ticket_metadata(
            ticket=ticket,
            actor=request.user,
            changes=serializer.validated_data,
        )
        return Response(
            TicketListSerializer(updated, context={"request": request}).data
        )

    def destroy(self, request, *args, **kwargs):
        # Ticket history is a business record. Closing/reopening is reversible;
        # hard deletion would invalidate the audit trail and attachment links.
        raise PermissionDenied("حذف تیکت مجاز نیست؛ تیکت را ببندید یا بایگانی کنید.")

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        ticket = self.get_object()
        try:
            mark_read(ticket=ticket, actor=request.user)
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response({"success": True, "isRead": True})

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        ticket = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request, "ticket": ticket},
        )
        serializer.is_valid(raise_exception=True)
        try:
            updated, _message = add_message(
                ticket=ticket,
                actor=request.user,
                body=serializer.validated_data["message"],
                thread_recipient_id=serializer.validated_data.get(
                    "thread_recipient_id"
                ),
                attachments=serializer.validated_data.get("attachments") or [],
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except (ValueError, DjangoValidationError) as exc:
            detail = (
                getattr(exc, "message_dict", None)
                or getattr(exc, "messages", None)
                or str(exc)
            )
            raise serializers.ValidationError(detail) from exc

        # Reuse retrieve's visibility logic without an extra notification or
        # read-audit event; the actor's own reply is already read for them.
        messages = (
            TicketMessage.objects.filter(ticket=updated)
            .select_related("sender", "thread_recipient")
            .prefetch_related("attachments")
        )
        if (
            getattr(request.user, "role", "") != "ADMIN"
            and updated.created_by_id != request.user.pk
        ):
            messages = messages.filter(
                Q(thread_recipient__isnull=True)
                | Q(thread_recipient_id=request.user.pk)
            )
        updated._visible_messages = messages.order_by("created_at", "id")
        return Response(
            TicketDetailSerializer(updated, context={"request": request}).data
        )

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        ticket = self.get_object()
        try:
            updated = close_ticket(ticket=ticket, actor=request.user)
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(
            TicketListSerializer(updated, context={"request": request}).data
        )

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        ticket = self.get_object()
        try:
            updated = reopen_ticket(ticket=ticket, actor=request.user)
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(
            TicketListSerializer(updated, context={"request": request}).data
        )

    @action(detail=True, methods=["get"])
    def audit(self, request, pk=None):
        ticket = self.get_object()
        events = list(ticket.audit_events.select_related("actor", "ticket").all())
        if (
            getattr(request.user, "role", "") != "ADMIN"
            and ticket.created_by_id != request.user.pk
        ):
            visible_events = []
            for event in events:
                metadata = event.metadata or {}
                if event.action == "REPLIED":
                    target = metadata.get("thread_recipient_id")
                    if target not in (None, request.user.pk):
                        continue
                if event.action == "READ" and event.actor_id != request.user.pk:
                    continue
                visible_events.append(event)
            events = visible_events
        return Response(
            TicketAuditSerializer(events, many=True, context={"request": request}).data
        )

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = request.user.ticket_participations.filter(is_read=False).count()
        return Response({"count": count})

    @action(detail=False, methods=["get"])
    def export(self, request):
        if getattr(request.user, "role", "") != "ADMIN":
            raise PermissionDenied("فقط مدیران می‌توانند خروجی تیکت‌ها را دریافت کنند.")
        queryset = self.filter_queryset(self.get_queryset())

        def safe_csv(value):
            text = "" if value is None else str(value)
            # Prevent spreadsheet formula injection when user-controlled titles
            # are opened in Excel/LibreOffice.
            return f"'{text}" if text[:1] in {"=", "+", "-", "@"} else text

        def stream():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "شماره تیکت",
                    "عنوان",
                    "نوع",
                    "موضوع",
                    "وضعیت",
                    "اولویت",
                    "ثبت‌کننده",
                    "گیرندگان",
                    "تعداد پاسخ",
                    "مهلت پاسخ",
                    "تاریخ ایجاد",
                    "آخرین بروزرسانی",
                ]
            )
            yield "\ufeff" + output.getvalue()
            for ticket in queryset.iterator(chunk_size=200):
                output.seek(0)
                output.truncate(0)
                recipients = [
                    user_display_name(p.user)
                    for p in getattr(ticket, "_ticket_participants", [])
                    if p.role == TicketParticipantRole.RECIPIENT
                ]
                writer.writerow(
                    [
                        safe_csv(ticket.ticket_number),
                        safe_csv(ticket.title),
                        safe_csv(ticket.get_ticket_type_display()),
                        safe_csv(
                            dict(TicketSubject.choices).get(
                                ticket.subject_type, ticket.subject_type
                            )
                        ),
                        safe_csv(ticket.get_status_display()),
                        safe_csv(ticket.get_priority_display()),
                        safe_csv(user_display_name(ticket.created_by)),
                        safe_csv("، ".join(recipients)),
                        safe_csv(ticket.reply_count),
                        safe_csv(
                            ticket.sla_due_at.isoformat() if ticket.sla_due_at else ""
                        ),
                        safe_csv(
                            ticket.created_at.isoformat() if ticket.created_at else ""
                        ),
                        safe_csv(
                            ticket.updated_at.isoformat() if ticket.updated_at else ""
                        ),
                    ]
                )
                yield output.getvalue()

        log_activity(
            user=request.user,
            action="export",
            target_type="system",
            description="خروجی فهرست تیکت‌ها دریافت شد",
            metadata={"filters": dict(request.query_params.lists())},
        )
        response = StreamingHttpResponse(
            stream(), content_type="text/csv; charset=utf-8"
        )
        filename = quote("خروجی-تیکت‌ها.csv")
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
        return response


class TicketMetaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "subjects": [
                    {"value": value, "label": label}
                    for value, label in TicketSubject.choices
                ],
                "types": [
                    {"value": value, "label": label}
                    for value, label in TicketType.choices
                ],
                "priorities": [
                    {"value": value, "label": label}
                    for value, label in TicketPriority.choices
                ],
                "statuses": [
                    {"value": value, "label": label}
                    for value, label in TicketStatus.choices
                ],
                "defaultSlaHours": {
                    "NORMAL": 48,
                    "IMPORTANT": 24,
                    "URGENT": 4,
                },
            }
        )


class TicketSubjectOptionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        subject_type = (
            request.query_params.get("type")
            or request.query_params.get("subjectType")
            or ""
        ).upper()
        if subject_type not in {value for value, _ in TicketSubject.choices}:
            return Response(
                {"type": "نوع موضوع معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST
            )

        queryset = subject_queryset_for_user(request.user, subject_type)
        q = (request.query_params.get("q") or "").strip()
        if q:
            if subject_type == TicketSubject.PROPERTY:
                queryset = queryset.filter(
                    Q(title__icontains=q)
                    | Q(internal_code__icontains=q)
                    | Q(neighborhood__icontains=q)
                )
            elif subject_type == TicketSubject.LISTING:
                queryset = queryset.filter(
                    Q(title__icontains=q) | Q(property__title__icontains=q)
                )
            elif subject_type == TicketSubject.FOLLOWUP:
                queryset = queryset.filter(
                    Q(title__icontains=q) | Q(contact_name__icontains=q)
                )
            elif subject_type == TicketSubject.TASK:
                queryset = queryset.filter(
                    Q(title__icontains=q)
                    | Q(description__icontains=q)
                    | Q(assigned_to__first_name__icontains=q)
                    | Q(assigned_to__last_name__icontains=q)
                )
            elif subject_type == TicketSubject.TICKET:
                queryset = queryset.filter(
                    Q(ticket_number__icontains=q) | Q(title__icontains=q)
                )

        queryset = queryset.order_by("-pk")
        try:
            page = max(1, int(request.query_params.get("page", "1")))
            page_size = min(
                50, max(1, int(request.query_params.get("page_size", "25")))
            )
        except ValueError:
            return Response(
                {"page": "صفحه‌بندی معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST
            )
        count = queryset.count()
        start = (page - 1) * page_size
        rows = queryset[start : start + page_size]

        results = []
        for subject in rows:
            if subject_type == TicketSubject.PROPERTY:
                label = f"{subject.title} · {subject.internal_code}"
            elif subject_type == TicketSubject.LISTING:
                label = subject.title
                if getattr(subject, "property", None):
                    label += f" · {subject.property.title}"
            elif subject_type == TicketSubject.FOLLOWUP:
                label = f"{subject.title} · {subject.contact_name}"
            elif subject_type == TicketSubject.TASK:
                label = subject.title
            else:
                label = f"{subject.ticket_number} · {subject.title or 'بدون عنوان'}"
            result = {"id": subject.pk, "label": label}
            if subject_type == TicketSubject.PROPERTY:
                result.update({"title": subject.title, "code": subject.internal_code})
            elif subject_type == TicketSubject.LISTING:
                result.update(
                    {"title": subject.title, "propertyId": subject.property_id}
                )
            elif subject_type == TicketSubject.FOLLOWUP:
                result.update({"title": subject.title, "contact": subject.contact_name})
            elif subject_type == TicketSubject.TASK:
                result.update(
                    {"title": subject.title, "assignedToId": subject.assigned_to_id}
                )
            else:
                result.update(
                    {"title": subject.title, "ticketNumber": subject.ticket_number}
                )
            results.append(result)

        return Response(
            {
                "count": count,
                "page": page,
                "pageSize": page_size,
                "next": page + 1 if start + page_size < count else None,
                "previous": page - 1 if page > 1 and start < count else None,
                "results": results,
            }
        )


class TicketRecipientOptionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        is_admin = getattr(request.user, "role", "") == "ADMIN"
        include_self = (
            request.query_params.get("includeSelf") in {"true", "1", "yes"} and is_admin
        )
        include_inactive = (
            request.query_params.get("includeInactive") in {"true", "1", "yes"}
            and is_admin
        )
        if include_inactive:
            queryset = User.objects.filter(role__in=["ADMIN", "AGENT"])
            if not include_self:
                queryset = queryset.exclude(pk=request.user.pk)
            queryset = queryset.select_related(
                "consultant_profile", "admin_profile"
            ).order_by("first_name", "last_name", "username")
        else:
            queryset = active_recipient_queryset(None if include_self else request.user)
        q = (request.query_params.get("q") or "").strip()
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )
        try:
            limit = min(100, max(1, int(request.query_params.get("limit", "50"))))
        except ValueError:
            limit = 50
        return Response(TicketRecipientSerializer(queryset[:limit], many=True).data)


class TicketUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {"count": request.user.ticket_participations.filter(is_read=False).count()}
        )


class TicketAttachmentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from .models import TicketAttachment

        attachment = get_object_or_404(
            TicketAttachment.objects.select_related("message__ticket"), pk=pk
        )
        if not can_view_ticket(request.user, attachment.message.ticket):
            # Do not distinguish "missing" from "not yours" for opaque file
            # ids; it prevents an attachment-id oracle.
            raise Http404("پیوست یافت نشد.")
        if not attachment.file:
            return Response(
                {"detail": "فایل یافت نشد."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            file_handle = attachment.file.open("rb")
        except (FileNotFoundError, OSError):
            return Response(
                {"detail": "فایل یافت نشد."}, status=status.HTTP_404_NOT_FOUND
            )
        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=attachment.original_name,
            content_type="application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response
