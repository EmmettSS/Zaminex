"""REST serializers for the ticket workspace."""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .access import (
    active_recipient_queryset,
    can_view_ticket,
    get_subject_for_user,
    is_active_recipient,
    subject_is_accessible,
)
from .models import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    MAX_MESSAGE_LENGTH,
    MAX_TICKET_RECIPIENTS,
    MAX_TICKET_TAGS,
    MAX_TICKET_TAG_LENGTH,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketParticipantRole,
    TicketPriority,
    TicketStatus,
    TicketSubject,
    TicketType,
)


User = get_user_model()


def _parse_form_list(values):
    """Return a flat list from JSON, repeated, or comma-separated form values.

    ``QueryDict`` stores a value assigned with ``data["field"] = [..]`` as one
    item whose value is itself a list.  DRF then hands that nested value to a
    ``ListField`` child (for example an ``IntegerField``), which is the source
    of the misleading "valid number" error raised by the ticket form.

    This helper deliberately works with values obtained via ``getlist`` and
    returns an ordinary Python list.  It therefore supports browser FormData
    (`[4, 7]` as JSON), repeated form keys, and the comma-separated format used
    by a few older clients without mutating the incoming QueryDict.
    """

    parsed_values = []
    for value in values:
        # Native JSON requests already contain lists.  Unpack only this outer
        # list; a deliberately malformed deeper list is left to DRF's child
        # field validation instead of being silently coerced.
        if isinstance(value, (list, tuple)):
            parsed_values.extend(value)
            continue
        if not isinstance(value, str):
            parsed_values.append(value)
            continue

        text = value.strip()
        if not text:
            continue
        try:
            decoded = json.loads(text)
        except (TypeError, ValueError):
            # FormData has no native array primitive.  Supporting repeated
            # values above and comma-separated values here makes a one-item
            # recipient/tag input behave as a list as well.
            parsed_values.extend(
                part.strip() for part in text.split(",") if part.strip()
            )
        else:
            if isinstance(decoded, list):
                parsed_values.extend(decoded)
            else:
                parsed_values.append(decoded)
    return parsed_values


def _as_file_list(value):
    """Keep repeated multipart files as an ordinary list of UploadedFiles."""

    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _normalise_request_data(data, *, aliases, list_fields, file_fields=()):
    """Map API aliases and normalise multipart input without changing QueryDict.

    DRF hands multipart input to serializers as a QueryDict.  Assigning a
    Python list back through ``__setitem__`` nests it in that QueryDict.  Build
    a fresh, plain dictionary instead, keeping scalar values scalar and
    obtaining repeated values/files with ``getlist`` before any alias mapping.
    JSON requests are normal dictionaries and retain the same public aliases.
    """

    list_fields = set(list_fields)
    file_fields = set(file_fields)

    if hasattr(data, "getlist"):
        normalised = {}
        for source_key in data.keys():
            target_key = aliases.get(source_key, source_key)
            # The canonical field takes precedence when a caller sends both
            # spellings.  This matches the old mapping behaviour while making
            # the choice deterministic.
            if source_key in aliases and target_key in data:
                continue

            if target_key in list_fields:
                values = data.getlist(source_key)
                normalised[target_key] = (
                    _as_file_list(values)
                    if target_key in file_fields
                    else _parse_form_list(values)
                )
            else:
                # QueryDict.get returns one scalar (the last submitted value),
                # exactly what scalar DRF fields expect.
                normalised[target_key] = data.get(source_key)
        return normalised

    # JSONParser supplies a normal mapping.  Do not mutate it: serializers can
    # be reused and callers may hold a reference to request.data.
    normalised = dict(data)
    for source_key, target_key in aliases.items():
        if target_key not in normalised and source_key in normalised:
            normalised[target_key] = normalised[source_key]

    for key in list_fields:
        if key not in normalised:
            continue
        normalised[key] = (
            _as_file_list(normalised[key])
            if key in file_fields
            else _parse_form_list(_as_file_list(normalised[key]))
        )
    return normalised


def user_display_name(user) -> str:
    if not user:
        return "سیستم"
    profile = getattr(user, "consultant_profile", None) or getattr(
        user, "admin_profile", None
    )
    profile_name = (getattr(profile, "full_name", "") or "").strip()
    return profile_name or (user.get_full_name() or "").strip() or user.username


def user_summary(user) -> dict | None:
    if not user:
        return None
    return {
        "id": user.pk,
        "username": user.username,
        "name": user_display_name(user),
        "email": user.email,
        "role": user.role,
    }


def _subject_label(subject_type: str, subject) -> str:
    if subject is None:
        return "موضوع مرتبط"
    if subject_type == TicketSubject.PROPERTY:
        return f"{subject.title} · {subject.internal_code}"
    if subject_type == TicketSubject.LISTING:
        property_title = getattr(getattr(subject, "property", None), "title", "")
        return f"{subject.title}{f' · {property_title}' if property_title else ''}"
    if subject_type == TicketSubject.FOLLOWUP:
        return f"{subject.title} · {subject.contact_name}"
    if subject_type == TicketSubject.TASK:
        return subject.title
    if subject_type == TicketSubject.TICKET:
        return f"{subject.ticket_number or f'تیکت {subject.pk}'} · {subject.title or 'بدون عنوان'}"
    return str(subject)


def subject_summary(user, subject_type: str, subject) -> dict:
    """Return a deliberately small subject projection.

    A user may be allowed to read a ticket while not being allowed to read the
    linked record.  In that case callers must use the restricted projection,
    which contains no object id or business data.
    """

    type_label = dict(TicketSubject.choices).get(subject_type, "موضوع")
    if not subject_is_accessible(user, subject_type, subject):
        return {
            "type": subject_type,
            "typeLabel": type_label,
            "id": None,
            "label": "موضوع مرتبط (جزئیات محدود)",
            "restricted": True,
        }

    data = {
        "type": subject_type,
        "typeLabel": type_label,
        "id": subject.pk,
        "label": _subject_label(subject_type, subject),
        "restricted": False,
    }
    if subject_type == TicketSubject.PROPERTY:
        data.update({"title": subject.title, "internalCode": subject.internal_code})
    elif subject_type == TicketSubject.LISTING:
        data.update({"title": subject.title, "propertyId": subject.property_id})
    elif subject_type == TicketSubject.FOLLOWUP:
        data.update({"title": subject.title, "contact": subject.contact_name})
    elif subject_type == TicketSubject.TASK:
        data.update({"title": subject.title, "assignedToId": subject.assigned_to_id})
    elif subject_type == TicketSubject.TICKET:
        data.update({"title": subject.title, "ticketNumber": subject.ticket_number})
    return data


class TicketAttachmentSerializer(serializers.ModelSerializer):
    originalName = serializers.CharField(source="original_name", read_only=True)
    contentType = serializers.CharField(source="content_type", read_only=True)
    downloadUrl = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = TicketAttachment
        fields = [
            "id",
            "originalName",
            "contentType",
            "size",
            "downloadUrl",
            "createdAt",
        ]

    def get_downloadUrl(self, obj):
        return f"/tickets/api/attachments/{obj.pk}/download/"


class TicketMessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    threadRecipient = serializers.SerializerMethodField()
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    isInitial = serializers.BooleanField(source="is_initial", read_only=True)

    class Meta:
        model = TicketMessage
        fields = [
            "id",
            "body",
            "sender",
            "threadRecipient",
            "attachments",
            "createdAt",
            "isInitial",
        ]

    def get_sender(self, obj):
        return user_summary(obj.sender)

    def get_threadRecipient(self, obj):
        return user_summary(obj.thread_recipient)


class TicketListSerializer(serializers.ModelSerializer):
    ticketNumber = serializers.CharField(source="ticket_number", read_only=True)
    ticketType = serializers.CharField(source="ticket_type", read_only=True)
    ticketTypeLabel = serializers.SerializerMethodField()
    priorityLabel = serializers.SerializerMethodField()
    statusLabel = serializers.SerializerMethodField()
    subjectType = serializers.CharField(source="subject_type", read_only=True)
    subjectTypeLabel = serializers.SerializerMethodField()
    subjectId = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    createdBy = serializers.SerializerMethodField()
    recipients = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    hasReply = serializers.SerializerMethodField()
    replyCount = serializers.SerializerMethodField()
    lastMessageAt = serializers.DateTimeField(source="last_message_at", read_only=True)
    lastMessageSender = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    slaDueAt = serializers.DateTimeField(source="sla_due_at", read_only=True)
    isOverdue = serializers.BooleanField(source="is_overdue", read_only=True)
    isRead = serializers.SerializerMethodField()
    isUnread = serializers.SerializerMethodField()
    needsResponse = serializers.SerializerMethodField()
    waitingForLabel = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticketNumber",
            "title",
            "ticketType",
            "ticketTypeLabel",
            "priority",
            "priorityLabel",
            "status",
            "statusLabel",
            "subjectType",
            "subjectTypeLabel",
            "subjectId",
            "subject",
            "createdBy",
            "recipients",
            "tags",
            "hasReply",
            "replyCount",
            "lastMessageAt",
            "lastMessageSender",
            "createdAt",
            "updatedAt",
            "slaDueAt",
            "isOverdue",
            "isRead",
            "isUnread",
            "needsResponse",
            "waitingForLabel",
        ]

    def _viewer(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def _participants(self, obj):
        cached = getattr(obj, "_ticket_participants", None)
        if cached is not None:
            return cached
        return list(
            obj.participants.select_related("user", "last_visible_sender").all()
        )

    def _participant(self, obj):
        viewer = self._viewer()
        if not viewer or not getattr(viewer, "is_authenticated", False):
            return None
        for participant in self._participants(obj):
            if participant.user_id == viewer.pk:
                return participant
        return None

    def get_ticketTypeLabel(self, obj):
        return obj.get_ticket_type_display()

    def get_priorityLabel(self, obj):
        return obj.get_priority_display()

    def _viewer_reply_count(self, obj):
        viewer = self._viewer()
        participant = self._participant(obj)
        if (
            viewer
            and getattr(viewer, "role", "") != "ADMIN"
            and participant
            and participant.role == TicketParticipantRole.RECIPIENT
        ):
            return participant.visible_reply_count
        return obj.reply_count

    def get_status(self, obj):
        viewer = self._viewer()
        participant = self._participant(obj)
        if (
            viewer
            and getattr(viewer, "role", "") != "ADMIN"
            and participant
            and participant.role == TicketParticipantRole.RECIPIENT
            and obj.status != TicketStatus.CLOSED
        ):
            return (
                TicketStatus.ANSWERED
                if self._viewer_reply_count(obj)
                else TicketStatus.WAITING_REPLY
            )
        return obj.status

    def get_statusLabel(self, obj):
        return dict(TicketStatus.choices).get(
            self.get_status(obj), self.get_status(obj)
        )

    def get_hasReply(self, obj):
        return bool(self._viewer_reply_count(obj))

    def get_replyCount(self, obj):
        return self._viewer_reply_count(obj)

    def get_subjectTypeLabel(self, obj):
        return dict(TicketSubject.choices).get(obj.subject_type, obj.subject_type)

    def get_subject(self, obj):
        viewer = self._viewer()
        return subject_summary(viewer, obj.subject_type, obj.subject_object)

    def get_subjectId(self, obj):
        viewer = self._viewer()
        if subject_is_accessible(viewer, obj.subject_type, obj.subject_object):
            return obj.subject_id
        return None

    def get_createdBy(self, obj):
        return user_summary(obj.created_by)

    def get_recipients(self, obj):
        viewer = self._viewer()
        participants = [
            p
            for p in self._participants(obj)
            if p.role == TicketParticipantRole.RECIPIENT
        ]
        # A recipient must not learn who else received a private group ticket.
        if (
            viewer
            and not getattr(viewer, "role", "") == "ADMIN"
            and obj.created_by_id != viewer.pk
        ):
            participants = [p for p in participants if p.user_id == viewer.pk]
        return [user_summary(p.user) for p in participants]

    def get_lastMessageSender(self, obj):
        participant = self._participant(obj)
        viewer = self._viewer()
        if participant and viewer and obj.created_by_id != viewer.pk:
            return user_summary(participant.last_visible_sender)
        return user_summary(obj.last_message_sender)

    def get_isRead(self, obj):
        viewer = self._viewer()
        participant = self._participant(obj)
        if participant:
            return bool(participant.is_read)
        # Admin oversight rows are not an unread inbox item unless the admin is
        # an actual participant in the conversation.
        return True if viewer and getattr(viewer, "role", "") == "ADMIN" else False

    def get_isUnread(self, obj):
        return not self.get_isRead(obj)

    def get_needsResponse(self, obj):
        viewer = self._viewer()
        participant = self._participant(obj)
        if not viewer or not participant or obj.status == TicketStatus.CLOSED:
            return False
        return bool(
            participant.last_visible_sender_id
            and participant.last_visible_sender_id != viewer.pk
        )

    def get_waitingForLabel(self, obj):
        if self.get_status(obj) == TicketStatus.CLOSED:
            return "بسته"
        if self.get_needsResponse(obj):
            return "در انتظار پاسخ من"
        if self._viewer_reply_count(obj) == 0:
            return "بدون پاسخ"
        return "در انتظار پاسخ طرف مقابل"


class TicketDetailSerializer(TicketListSerializer):
    messages = serializers.SerializerMethodField()

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + ["messages"]

    def get_messages(self, obj):
        messages = getattr(obj, "_visible_messages", None)
        if messages is None:
            messages = (
                obj.messages.select_related("sender", "thread_recipient")
                .prefetch_related("attachments")
                .all()
            )
        return TicketMessageSerializer(
            messages,
            many=True,
            context=self.context,
        ).data


class TicketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    ticket_type = serializers.ChoiceField(
        choices=TicketType.choices, required=False, default=TicketType.OTHER
    )
    priority = serializers.ChoiceField(
        choices=TicketPriority.choices, required=False, default=TicketPriority.NORMAL
    )
    subject_type = serializers.ChoiceField(choices=TicketSubject.choices)
    subject_id = serializers.IntegerField(min_value=1)
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=MAX_TICKET_RECIPIENTS,
    )
    message = serializers.CharField(
        max_length=MAX_MESSAGE_LENGTH,
        allow_blank=False,
        trim_whitespace=True,
    )
    tags = serializers.ListField(
        child=serializers.CharField(
            max_length=MAX_TICKET_TAG_LENGTH, allow_blank=False
        ),
        required=False,
        allow_empty=True,
        max_length=MAX_TICKET_TAGS,
    )
    sla_due_at = serializers.DateTimeField(required=False, allow_null=True)
    attachments = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
        max_length=MAX_ATTACHMENTS_PER_MESSAGE,
        write_only=True,
    )

    def to_internal_value(self, data):
        data = _normalise_request_data(
            data,
            aliases={
                "ticketType": "ticket_type",
                "subjectType": "subject_type",
                "subjectId": "subject_id",
                "recipientIds": "recipient_ids",
                "slaDueAt": "sla_due_at",
            },
            list_fields={"recipient_ids", "tags", "attachments"},
            file_fields={"attachments"},
        )
        return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        subject = get_subject_for_user(user, attrs["subject_type"], attrs["subject_id"])
        if subject is None:
            raise serializers.ValidationError(
                {"subject_id": "به موضوع انتخاب‌شده دسترسی ندارید یا وجود ندارد."}
            )
        attrs["subject"] = subject

        ids = list(dict.fromkeys(attrs.get("recipient_ids") or []))
        if not ids:
            raise serializers.ValidationError(
                {"recipient_ids": "حداقل یک گیرنده انتخاب کنید."}
            )
        if len(ids) > MAX_TICKET_RECIPIENTS:
            raise serializers.ValidationError(
                {"recipient_ids": "تعداد گیرنده‌ها بیش از حد مجاز است."}
            )
        if user and user.pk in ids:
            raise serializers.ValidationError(
                {"recipient_ids": "ارسال تیکت برای حساب خودتان مجاز نیست."}
            )

        users = list(active_recipient_queryset().filter(pk__in=ids))
        by_id = {item.pk: item for item in users}
        invalid = [
            item
            for item in ids
            if item not in by_id or not is_active_recipient(by_id[item])
        ]
        if invalid:
            raise serializers.ValidationError(
                {"recipient_ids": "یکی از گیرنده‌ها معتبر یا فعال نیست."}
            )
        attrs["recipient_ids"] = ids
        attrs["recipients"] = [by_id[item] for item in ids]

        tags = []
        for tag in attrs.get("tags") or []:
            normalized = " ".join(str(tag).strip().split())
            if normalized and normalized not in tags:
                tags.append(normalized[:MAX_TICKET_TAG_LENGTH])
        attrs["tags"] = tags[:MAX_TICKET_TAGS]

        if not attrs.get("message", "").strip():
            raise serializers.ValidationError({"message": "متن پیام الزامی است."})
        return attrs


class TicketUpdateSerializer(serializers.Serializer):
    """Metadata-only update; messages and subjects are immutable."""

    title = serializers.CharField(required=False, allow_blank=False, max_length=255)
    priority = serializers.ChoiceField(choices=TicketPriority.choices, required=False)
    status = serializers.ChoiceField(choices=TicketStatus.choices, required=False)
    tags = serializers.ListField(
        child=serializers.CharField(
            max_length=MAX_TICKET_TAG_LENGTH, allow_blank=False
        ),
        required=False,
        allow_empty=True,
        max_length=MAX_TICKET_TAGS,
    )
    sla_due_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_tags(self, value):
        tags = []
        for tag in value:
            normalized = " ".join(str(tag).strip().split())
            if normalized and normalized not in tags:
                tags.append(normalized[:MAX_TICKET_TAG_LENGTH])
        return tags[:MAX_TICKET_TAGS]


class TicketReplySerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=MAX_MESSAGE_LENGTH,
        allow_blank=False,
        trim_whitespace=True,
    )
    thread_recipient_id = serializers.IntegerField(
        required=False, allow_null=True, min_value=1
    )
    attachments = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
        max_length=MAX_ATTACHMENTS_PER_MESSAGE,
        write_only=True,
    )

    def to_internal_value(self, data):
        data = _normalise_request_data(
            data,
            aliases={
                "body": "message",
                "threadRecipientId": "thread_recipient_id",
            },
            list_fields={"attachments"},
            file_fields={"attachments"},
        )
        return super().to_internal_value(data)

    def validate(self, attrs):
        ticket = self.context.get("ticket")
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not ticket or not user or not can_view_ticket(user, ticket):
            raise serializers.ValidationError("به این تیکت دسترسی ندارید.")

        recipient_ids = list(
            ticket.participants.filter(
                role=TicketParticipantRole.RECIPIENT
            ).values_list("user_id", flat=True)
        )
        target = attrs.get("thread_recipient_id")
        if ticket.created_by_id == user.pk:
            if target is None and len(recipient_ids) == 1:
                target = recipient_ids[0]
            if target is not None and target not in recipient_ids:
                raise serializers.ValidationError(
                    {"thread_recipient_id": "گیرنده این رشته معتبر نیست."}
                )
        elif user.pk in recipient_ids:
            # Recipients can only answer their own private branch.
            if target is not None and target != user.pk:
                raise serializers.ValidationError(
                    {"thread_recipient_id": "پاسخ خصوصی فقط برای رشته خودتان مجاز است."}
                )
            target = user.pk
        elif getattr(user, "role", "") == "ADMIN":
            # An overseeing admin may publish a common reply (NULL) or target
            # one known recipient.  This does not reveal the private messages
            # of one branch to another recipient.
            if target is not None and target not in recipient_ids:
                raise serializers.ValidationError(
                    {"thread_recipient_id": "گیرنده این رشته معتبر نیست."}
                )
        else:
            raise serializers.ValidationError("به این تیکت دسترسی ندارید.")

        attrs["thread_recipient_id"] = target
        if not attrs.get("message", "").strip():
            raise serializers.ValidationError({"message": "متن پاسخ الزامی است."})
        return attrs


class TicketRecipientSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "name", "email", "role"]

    def get_name(self, obj):
        return user_display_name(obj)


class TicketAuditSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    actionLabel = serializers.CharField(source="get_action_display", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        if (
            viewer
            and getattr(viewer, "role", "") != "ADMIN"
            and instance.ticket.created_by_id != viewer.pk
        ):
            metadata = dict(data.get("metadata") or {})
            if "recipient_ids" in metadata:
                metadata["recipient_ids"] = [viewer.pk]
            data["metadata"] = metadata
        return data

    class Meta:
        from .models import TicketAuditEvent

        model = TicketAuditEvent
        fields = ["id", "action", "actionLabel", "actor", "metadata", "createdAt"]

    def get_actor(self, obj):
        return user_summary(obj.actor)
