"""Transactional ticket operations.

All mutations pass through this module so counters, private-thread read state,
notifications and audit records cannot drift apart when a request fails halfway
through.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from apps.common.activity import log_activity
from apps.common.models import Notification

from .access import can_view_ticket
from .models import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    MAX_MESSAGE_LENGTH,
    Ticket,
    TicketAttachment,
    TicketAuditAction,
    TicketAuditEvent,
    TicketMessage,
    TicketParticipant,
    TicketParticipantRole,
    TicketPriority,
    TicketStatus,
    TicketSubject,
    validate_ticket_file,
)


SLA_HOURS = {
    TicketPriority.NORMAL: 48,
    TicketPriority.IMPORTANT: 24,
    TicketPriority.URGENT: 4,
}


def default_sla_due_at(priority: str):
    return timezone.now() + timedelta(
        hours=SLA_HOURS.get(priority, SLA_HOURS[TicketPriority.NORMAL])
    )


def _user_display_name(user) -> str:
    if not user:
        return "سیستم"
    profile = getattr(user, "consultant_profile", None) or getattr(
        user, "admin_profile", None
    )
    return (
        (getattr(profile, "full_name", "") or "").strip()
        or (user.get_full_name() or "").strip()
        or user.username
    )


def _safe_original_name(uploaded_file) -> str:
    name = Path(str(getattr(uploaded_file, "name", "پیوست"))).name
    # Keep the original display name useful while stripping control characters
    # and path separators. Storage itself always uses an opaque UUID name.
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255] or "پیوست"


def _validate_attachments(files):
    files = list(files or [])
    if len(files) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise ValueError("حداکثر ۵ پیوست برای هر پیام مجاز است.")
    for uploaded_file in files:
        validate_ticket_file(uploaded_file)
    return files


def _create_attachments(message: TicketMessage, files):
    attachments = []
    for uploaded_file in _validate_attachments(files):
        attachment = TicketAttachment(
            message=message,
            file=uploaded_file,
            original_name=_safe_original_name(uploaded_file),
            content_type=(getattr(uploaded_file, "content_type", "") or "")[:100],
            size=int(getattr(uploaded_file, "size", 0) or 0),
        )
        # Run model-level validators before writing the opaque storage object.
        attachment.full_clean(exclude=["message"])
        attachment.save(force_insert=True)
        attachments.append(attachment)
    return attachments


def _subject_field(subject_type: str) -> str:
    return {
        TicketSubject.PROPERTY: "property",
        TicketSubject.LISTING: "listing",
        TicketSubject.FOLLOWUP: "followup",
        TicketSubject.TASK: "task",
        TicketSubject.TICKET: "related_ticket",
    }[subject_type]


def _subject_title(subject_type: str, subject) -> str:
    if subject_type == TicketSubject.PROPERTY:
        return f"{subject.title} · {subject.internal_code}"
    if subject_type == TicketSubject.LISTING:
        return subject.title
    if subject_type == TicketSubject.FOLLOWUP:
        return subject.title
    if subject_type == TicketSubject.TASK:
        return subject.title
    if subject_type == TicketSubject.TICKET:
        return f"پیگیری {subject.ticket_number or f'تیکت {subject.pk}'}"
    return "تیکت جدید"


def _audit(ticket: Ticket, actor, action: str, metadata: dict | None = None):
    event = TicketAuditEvent.objects.create(
        ticket=ticket,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        metadata=metadata or {},
    )
    # The global activity feed is useful to administrators; failures there must
    # never roll back the ticket operation (the ticket audit is authoritative).
    action_map = {
        TicketAuditAction.CREATED: "create",
        TicketAuditAction.REPLIED: "update",
        TicketAuditAction.READ: "update",
        TicketAuditAction.CLOSED: "archive",
        TicketAuditAction.REOPENED: "status_change",
        TicketAuditAction.UPDATED: "update",
        TicketAuditAction.RECIPIENT_ADDED: "update",
    }
    log_activity(
        user=actor,
        action=action_map.get(action, "update"),
        target_type="ticket",
        target_id=ticket.pk,
        description=f"{ticket.ticket_number or 'تیکت'}: {dict(TicketAuditAction.choices).get(action, action)}",
        metadata={"ticket_number": ticket.ticket_number, **(metadata or {})},
    )
    return event


def _notify(
    user,
    notification_type: str,
    title: str,
    message: str,
    ticket: Ticket,
    *,
    folder: str,
):
    if not user or user.pk is None:
        return
    Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        message=message,
        metadata={
            "ticketId": ticket.pk,
            "ticketNumber": ticket.ticket_number,
            "ticketFolder": folder,
        },
    )


def _conversation_participants(ticket):
    return list(ticket.participants.select_related("user"))


def _set_initial_participant_state(
    ticket: Ticket, initial_message: TicketMessage, recipients
):
    now = initial_message.created_at or timezone.now()
    participants = [
        TicketParticipant(
            ticket=ticket,
            user=ticket.created_by,
            role=TicketParticipantRole.OWNER,
            is_read=True,
            read_at=now,
            last_visible_message_at=now,
            last_visible_sender=ticket.created_by,
        )
    ]
    participants.extend(
        TicketParticipant(
            ticket=ticket,
            user=recipient,
            role=TicketParticipantRole.RECIPIENT,
            is_read=False,
            read_at=None,
            last_visible_message_at=now,
            last_visible_sender=ticket.created_by,
        )
        for recipient in recipients
    )
    TicketParticipant.objects.bulk_create(participants)


@transaction.atomic
def create_ticket(*, actor, validated_data):
    """Create a ticket, its initial message, participants and notifications."""

    subject = validated_data["subject"]
    subject_type = validated_data["subject_type"]
    recipients = validated_data["recipients"]
    attachments = validated_data.get("attachments") or []

    title = (validated_data.get("title") or "").strip() or _subject_title(
        subject_type, subject
    )
    ticket = Ticket.objects.create(
        title=title,
        ticket_type=validated_data.get("ticket_type") or "OTHER",
        priority=validated_data.get("priority") or TicketPriority.NORMAL,
        status=TicketStatus.WAITING_REPLY,
        subject_type=subject_type,
        subject_id=subject.pk,
        **{_subject_field(subject_type): subject},
        created_by=actor,
        tags=validated_data.get("tags") or [],
        sla_due_at=validated_data.get("sla_due_at")
        or default_sla_due_at(validated_data.get("priority")),
    )

    initial = TicketMessage.objects.create(
        ticket=ticket,
        sender=actor,
        thread_recipient=None,
        body=validated_data["message"].strip(),
        is_initial=True,
    )
    _create_attachments(initial, attachments)
    _set_initial_participant_state(ticket, initial, recipients)

    ticket.last_message_at = initial.created_at
    ticket.last_message_sender = actor
    ticket.save(update_fields=["last_message_at", "last_message_sender", "updated_at"])

    _audit(
        ticket,
        actor,
        TicketAuditAction.CREATED,
        {
            "subject_type": subject_type,
            "subject_id": subject.pk,
            "recipient_ids": [recipient.pk for recipient in recipients],
            "ticket_type": ticket.ticket_type,
            "priority": ticket.priority,
        },
    )
    for recipient in recipients:
        _notify(
            recipient,
            "ticket_created",
            "تیکت جدید",
            f"تیکت {ticket.ticket_number} از طرف {_user_display_name(actor)} برای شما ثبت شد.",
            ticket,
            folder="received",
        )
    return ticket


@transaction.atomic
def add_message(
    *, ticket: Ticket, actor, body: str, thread_recipient_id=None, attachments=None
):
    """Append a reply and update only the participants who can see it."""

    locked_ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if not can_view_ticket(actor, locked_ticket):
        raise PermissionError("به این تیکت دسترسی ندارید.")

    body = (body or "").strip()
    if not body:
        raise ValueError("متن پاسخ الزامی است.")
    if len(body) > MAX_MESSAGE_LENGTH:
        raise ValueError("متن پیام نباید بیشتر از ۱۰٬۰۰۰ کاراکتر باشد.")
    files = _validate_attachments(attachments)

    message = TicketMessage.objects.create(
        ticket=locked_ticket,
        sender=actor,
        thread_recipient_id=thread_recipient_id,
        body=body,
        is_initial=False,
    )
    _create_attachments(message, files)

    participants = list(
        locked_ticket.participants.select_for_update().select_related("user")
    )
    now = message.created_at or timezone.now()
    visible_participants = []
    for participant in participants:
        visible = (
            thread_recipient_id is None
            or participant.user_id == locked_ticket.created_by_id
            or participant.user_id == thread_recipient_id
        )
        if not visible:
            continue
        visible_participants.append(participant)
        participant.last_visible_message_at = now
        participant.last_visible_sender = actor
        participant.visible_reply_count += 1
        if participant.user_id == actor.pk:
            participant.is_read = True
            participant.read_at = now
        else:
            participant.is_read = False
            participant.read_at = None
        participant.save(
            update_fields=[
                "last_visible_message_at",
                "last_visible_sender",
                "visible_reply_count",
                "is_read",
                "read_at",
            ]
        )

    locked_ticket.reply_count += 1
    locked_ticket.last_message_at = now
    locked_ticket.last_message_sender = actor
    # A new message is an explicit reopening operation. Once there is a reply,
    # the global ticket is considered answered while participants retain their
    # own needsResponse/read state.
    locked_ticket.status = TicketStatus.ANSWERED
    locked_ticket.closed_at = None
    locked_ticket.closed_by = None
    locked_ticket.save(
        update_fields=[
            "reply_count",
            "last_message_at",
            "last_message_sender",
            "status",
            "closed_at",
            "closed_by",
            "updated_at",
        ]
    )

    _audit(
        locked_ticket,
        actor,
        TicketAuditAction.REPLIED,
        {
            "message_id": message.pk,
            "thread_recipient_id": thread_recipient_id,
            "attachment_count": len(files),
        },
    )
    for participant in visible_participants:
        if participant.user_id == actor.pk:
            continue
        _notify(
            participant.user,
            "ticket_reply",
            "پاسخ جدید تیکت",
            f"در تیکت {locked_ticket.ticket_number} پاسخ جدیدی ارسال شد.",
            locked_ticket,
            folder=(
                "sent"
                if participant.role == TicketParticipantRole.OWNER
                else "received"
            ),
        )
    return locked_ticket, message


@transaction.atomic
def update_ticket_metadata(*, ticket: Ticket, actor, changes: dict):
    """Allow an administrator to edit metadata without touching messages."""

    locked_ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    old_status = locked_ticket.status
    before = {}
    for field in ("title", "priority", "status", "tags", "sla_due_at"):
        if field in changes:
            value = getattr(locked_ticket, field)
            before[field] = value.isoformat() if hasattr(value, "isoformat") else value
            setattr(locked_ticket, field, changes[field])

    if "status" in changes:
        if changes["status"] == TicketStatus.CLOSED:
            locked_ticket.closed_at = timezone.now()
            locked_ticket.closed_by = actor
        else:
            locked_ticket.closed_at = None
            locked_ticket.closed_by = None
    locked_ticket.save(
        update_fields=[*changes.keys(), "closed_at", "closed_by", "updated_at"]
    )

    after = {}
    for field in changes:
        value = getattr(locked_ticket, field)
        after[field] = value.isoformat() if hasattr(value, "isoformat") else value
    _audit(
        locked_ticket,
        actor,
        TicketAuditAction.UPDATED,
        {"before": before, "after": after},
    )
    if "status" in changes and old_status != locked_ticket.status:
        for participant in _conversation_participants(locked_ticket):
            if participant.user_id != actor.pk:
                _notify(
                    participant.user,
                    "ticket_status_changed",
                    "تغییر وضعیت تیکت",
                    f"وضعیت تیکت {locked_ticket.ticket_number} تغییر کرد.",
                    locked_ticket,
                    folder=(
                        "sent"
                        if participant.role == TicketParticipantRole.OWNER
                        else "received"
                    ),
                )
    return locked_ticket


@transaction.atomic
def mark_read(*, ticket: Ticket, actor) -> bool:
    locked_ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if not can_view_ticket(actor, locked_ticket):
        raise PermissionError("به این تیکت دسترسی ندارید.")
    participant = locked_ticket.participants.filter(user_id=actor.pk).first()
    if participant is None or participant.is_read:
        return False
    now = timezone.now()
    participant.is_read = True
    participant.read_at = now
    participant.save(update_fields=["is_read", "read_at"])
    _audit(locked_ticket, actor, TicketAuditAction.READ, {})
    return True


@transaction.atomic
def close_ticket(*, ticket: Ticket, actor):
    locked_ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if not can_view_ticket(actor, locked_ticket):
        raise PermissionError("به این تیکت دسترسی ندارید.")
    now = timezone.now()
    locked_ticket.status = TicketStatus.CLOSED
    locked_ticket.closed_at = now
    locked_ticket.closed_by = actor
    locked_ticket.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    _audit(locked_ticket, actor, TicketAuditAction.CLOSED, {})
    for participant in _conversation_participants(locked_ticket):
        if participant.user_id != actor.pk:
            _notify(
                participant.user,
                "ticket_status_changed",
                "تغییر وضعیت تیکت",
                f"تیکت {locked_ticket.ticket_number} بسته شد.",
                locked_ticket,
                folder=(
                    "sent"
                    if participant.role == TicketParticipantRole.OWNER
                    else "received"
                ),
            )
    return locked_ticket


@transaction.atomic
def reopen_ticket(*, ticket: Ticket, actor):
    locked_ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if not can_view_ticket(actor, locked_ticket):
        raise PermissionError("به این تیکت دسترسی ندارید.")
    locked_ticket.status = (
        TicketStatus.ANSWERED
        if locked_ticket.reply_count
        else TicketStatus.WAITING_REPLY
    )
    locked_ticket.closed_at = None
    locked_ticket.closed_by = None
    locked_ticket.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    _audit(locked_ticket, actor, TicketAuditAction.REOPENED, {})
    for participant in _conversation_participants(locked_ticket):
        if participant.user_id != actor.pk:
            _notify(
                participant.user,
                "ticket_status_changed",
                "بازگشایی تیکت",
                f"تیکت {locked_ticket.ticket_number} دوباره باز شد.",
                locked_ticket,
                folder=(
                    "sent"
                    if participant.role == TicketParticipantRole.OWNER
                    else "received"
                ),
            )
    return locked_ticket
