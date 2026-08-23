"""Models for the internal Zaminex ticketing workspace.

A ticket is an immutable, auditable conversation.  The ticket itself carries
its business metadata and one or more recipients.  Messages are append-only;
when a ticket has multiple recipients, replies can be private to the creator
and the recipient they address.  Object-level access is enforced in
``apps.tickets.access`` and in the API serializers, never only in the UI.
"""

from __future__ import annotations

import builtins
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class TicketSubject(models.TextChoices):
    PROPERTY = "PROPERTY", "املاک موجود"
    LISTING = "LISTING", "آگهی‌های موجود"
    FOLLOWUP = "FOLLOWUP", "پیگیری‌های موجود"
    TASK = "TASK", "وظایف موجود"
    TICKET = "TICKET", "تیکت‌های موجود"


class TicketType(models.TextChoices):
    QUESTION = "QUESTION", "پرسش"
    REQUEST = "REQUEST", "درخواست"
    ALERT = "ALERT", "هشدار"
    ISSUE = "ISSUE", "گزارش مشکل"
    COMPLAINT = "COMPLAINT", "شکایت"
    ANNOUNCEMENT = "ANNOUNCEMENT", "اطلاع‌رسانی"
    OTHER = "OTHER", "سایر"


class TicketPriority(models.TextChoices):
    NORMAL = "NORMAL", "عادی"
    IMPORTANT = "IMPORTANT", "مهم"
    URGENT = "URGENT", "فوری"


class TicketStatus(models.TextChoices):
    OPEN = "OPEN", "باز"
    WAITING_REPLY = "WAITING_REPLY", "در انتظار پاسخ"
    ANSWERED = "ANSWERED", "پاسخ‌داده‌شده"
    CLOSED = "CLOSED", "بسته"


class TicketParticipantRole(models.TextChoices):
    OWNER = "OWNER", "ثبت‌کننده"
    RECIPIENT = "RECIPIENT", "گیرنده"


class TicketAuditAction(models.TextChoices):
    CREATED = "CREATED", "ایجاد تیکت"
    REPLIED = "REPLIED", "ارسال پاسخ"
    READ = "READ", "مشاهده تیکت"
    CLOSED = "CLOSED", "بستن تیکت"
    REOPENED = "REOPENED", "بازگشایی تیکت"
    UPDATED = "UPDATED", "ویرایش تیکت"
    RECIPIENT_ADDED = "RECIPIENT_ADDED", "افزودن گیرنده"


ALLOWED_ATTACHMENT_EXTENSIONS = ("pdf", "jpg", "jpeg", "png", "webp")
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_MESSAGE = 5
MAX_MESSAGE_LENGTH = 10_000
MAX_TICKET_RECIPIENTS = 50
MAX_TICKET_TAGS = 10
MAX_TICKET_TAG_LENGTH = 40


def _extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def _has_expected_signature(extension: str, header: bytes) -> bool:
    """Reject files whose bytes do not match their declared safe extension.

    This is intentionally small and deterministic.  It is not a replacement
    for antivirus scanning, but it prevents the most common content-type and
    extension spoofing attacks before a file reaches protected storage.
    """

    if extension == "pdf":
        return header.startswith(b"%PDF-")
    if extension in {"jpg", "jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == "webp":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return False


def validate_ticket_file(uploaded_file):
    """Validate one ticket attachment at the model boundary.

    The validator works for both in-memory and temporary uploaded files and
    restores the current stream position afterwards so Django can persist it.
    """

    if uploaded_file is None:
        return

    size = getattr(uploaded_file, "size", None)
    if size is None or size <= 0:
        raise ValidationError("فایل پیوست خالی است.")
    if size > MAX_ATTACHMENT_SIZE:
        raise ValidationError("حجم هر پیوست نباید بیشتر از ۱۰ مگابایت باشد.")

    extension = _extension(getattr(uploaded_file, "name", ""))
    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError(
            "نوع فایل مجاز نیست. فقط PDF، JPG، PNG و WEBP قابل ارسال است."
        )

    try:
        position = uploaded_file.tell()
        uploaded_file.seek(0)
        header = uploaded_file.read(16)
        uploaded_file.seek(position)
    except (AttributeError, OSError) as exc:
        raise ValidationError("خواندن فایل پیوست ممکن نیست.") from exc

    if not _has_expected_signature(extension, header):
        raise ValidationError("محتوای فایل با پسوند آن مطابقت ندارد.")


def ticket_attachment_upload_to(instance, filename: str) -> str:
    """Use an opaque storage name; the original name is stored separately."""

    extension = _extension(filename)
    suffix = f".{extension}" if extension else ""
    now = timezone.now()
    return f"tickets/attachments/{now:%Y/%m}/{uuid4().hex}{suffix}"


class Ticket(models.Model):
    """Conversation metadata and the immutable business subject."""

    ticket_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        blank=True,
        null=True,
        verbose_name="شماره تیکت",
    )
    title = models.CharField(max_length=255, blank=True, verbose_name="عنوان تیکت")
    ticket_type = models.CharField(
        max_length=20,
        choices=TicketType.choices,
        default=TicketType.OTHER,
        db_index=True,
        verbose_name="نوع تیکت",
    )
    priority = models.CharField(
        max_length=20,
        choices=TicketPriority.choices,
        default=TicketPriority.NORMAL,
        db_index=True,
        verbose_name="اولویت",
    )
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.WAITING_REPLY,
        db_index=True,
        verbose_name="وضعیت",
    )
    subject_type = models.CharField(
        max_length=20,
        choices=TicketSubject.choices,
        db_index=True,
        verbose_name="موضوع تیکت",
    )
    subject_id = models.PositiveBigIntegerField(verbose_name="شناسه موضوع")

    # One concrete nullable FK per supported subject gives PostgreSQL a real
    # referential constraint instead of an unbounded GenericForeignKey.  The
    # CHECK constraint below makes sure exactly the selected field is present.
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.PROTECT,
        related_name="tickets",
        null=True,
        blank=True,
        verbose_name="ملک مرتبط",
    )
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.PROTECT,
        related_name="tickets",
        null=True,
        blank=True,
        verbose_name="آگهی مرتبط",
    )
    followup = models.ForeignKey(
        "followups.FollowUp",
        on_delete=models.PROTECT,
        related_name="tickets",
        null=True,
        blank=True,
        verbose_name="پیگیری مرتبط",
    )
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.PROTECT,
        related_name="tickets",
        null=True,
        blank=True,
        verbose_name="وظیفه مرتبط",
    )
    related_ticket = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="child_tickets",
        null=True,
        blank=True,
        verbose_name="تیکت مرتبط",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tickets",
        verbose_name="ثبت‌کننده",
    )
    tags = ArrayField(
        models.CharField(max_length=MAX_TICKET_TAG_LENGTH),
        default=list,
        blank=True,
        verbose_name="برچسب‌ها",
    )
    sla_due_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="مهلت پاسخ"
    )
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ بستن")
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="closed_tickets",
        null=True,
        blank=True,
        verbose_name="بسته‌شده توسط",
    )

    # Denormalized conversation counters keep list filters and sorting cheap.
    # They are updated only by the ticket service inside a row lock.
    reply_count = models.PositiveIntegerField(default=0, verbose_name="تعداد پاسخ")
    last_message_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="آخرین پیام"
    )
    last_message_sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="last_ticket_messages",
        null=True,
        blank=True,
        verbose_name="فرستنده آخرین پیام",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")

    class Meta:
        verbose_name = "تیکت"
        verbose_name_plural = "تیکت‌ها"
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(
                fields=["created_by", "-created_at"], name="ticket_creator_created_idx"
            ),
            models.Index(
                fields=["subject_type", "subject_id"], name="ticket_subject_idx"
            ),
            models.Index(
                fields=["status", "-updated_at"], name="ticket_status_updated_idx"
            ),
            models.Index(
                fields=["priority", "-updated_at"], name="ticket_priority_updated_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(subject_type=TicketSubject.PROPERTY)
                        & models.Q(property__isnull=False)
                        & models.Q(listing__isnull=True)
                        & models.Q(followup__isnull=True)
                        & models.Q(task__isnull=True)
                        & models.Q(related_ticket__isnull=True)
                    )
                    | (
                        models.Q(subject_type=TicketSubject.LISTING)
                        & models.Q(property__isnull=True)
                        & models.Q(listing__isnull=False)
                        & models.Q(followup__isnull=True)
                        & models.Q(task__isnull=True)
                        & models.Q(related_ticket__isnull=True)
                    )
                    | (
                        models.Q(subject_type=TicketSubject.FOLLOWUP)
                        & models.Q(property__isnull=True)
                        & models.Q(listing__isnull=True)
                        & models.Q(followup__isnull=False)
                        & models.Q(task__isnull=True)
                        & models.Q(related_ticket__isnull=True)
                    )
                    | (
                        models.Q(subject_type=TicketSubject.TASK)
                        & models.Q(property__isnull=True)
                        & models.Q(listing__isnull=True)
                        & models.Q(followup__isnull=True)
                        & models.Q(task__isnull=False)
                        & models.Q(related_ticket__isnull=True)
                    )
                    | (
                        models.Q(subject_type=TicketSubject.TICKET)
                        & models.Q(property__isnull=True)
                        & models.Q(listing__isnull=True)
                        & models.Q(followup__isnull=True)
                        & models.Q(task__isnull=True)
                        & models.Q(related_ticket__isnull=False)
                    )
                ),
                name="ticket_exactly_one_subject",
            ),
        ]

    def __str__(self) -> str:
        return self.ticket_number or f"تیکت {self.pk or 'جدید'}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.ticket_number:
            self.ticket_number = f"TKT-{self.pk:08d}"
            type(self).objects.filter(pk=self.pk).update(
                ticket_number=self.ticket_number
            )

    @builtins.property
    def has_reply(self) -> bool:
        return self.reply_count > 0

    @builtins.property
    def is_overdue(self) -> bool:
        return bool(
            self.sla_due_at
            and self.sla_due_at < timezone.now()
            and self.status != TicketStatus.CLOSED
        )

    @builtins.property
    def subject_object(self):
        return {
            TicketSubject.PROPERTY: self.property,
            TicketSubject.LISTING: self.listing,
            TicketSubject.FOLLOWUP: self.followup,
            TicketSubject.TASK: self.task,
            TicketSubject.TICKET: self.related_ticket,
        }.get(self.subject_type)


class TicketParticipant(models.Model):
    """Per-user read state and last visible activity for a ticket.

    The owner is also represented here.  This makes unread replies and private
    multi-recipient threads queryable without special cases or a client-side
    guess about who has seen a message.
    """

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="تیکت",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_participations",
        verbose_name="کاربر",
    )
    role = models.CharField(
        max_length=12, choices=TicketParticipantRole.choices, verbose_name="نقش"
    )
    is_read = models.BooleanField(
        default=False, db_index=True, verbose_name="خوانده شده"
    )
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ مشاهده")
    last_visible_message_at = models.DateTimeField(
        null=True, blank=True, verbose_name="آخرین پیام قابل مشاهده"
    )
    visible_reply_count = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد پاسخ‌های قابل مشاهده",
    )
    last_visible_sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ticket_visible_last_senders",
        null=True,
        blank=True,
        verbose_name="فرستنده آخرین پیام قابل مشاهده",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ عضویت")

    class Meta:
        verbose_name = "عضو تیکت"
        verbose_name_plural = "اعضای تیکت"
        constraints = [
            models.UniqueConstraint(
                fields=["ticket", "user"], name="ticket_unique_participant"
            ),
            models.UniqueConstraint(
                fields=["ticket"],
                condition=models.Q(role=TicketParticipantRole.OWNER),
                name="ticket_single_owner",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_read"], name="ticket_part_user_read_idx"),
            models.Index(fields=["ticket", "role"], name="ticket_part_ticket_role_idx"),
            models.Index(
                fields=["user", "last_visible_sender"],
                name="ticket_part_user_sender_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ticket} / {self.user}"


class TicketMessage(models.Model):
    """Append-only message. ``thread_recipient`` scopes private replies."""

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="messages", verbose_name="تیکت"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_messages",
        verbose_name="فرستنده",
    )
    # NULL means a common message visible to every participant.  A value means
    # only the owner, the addressed recipient and an admin auditor may see it.
    thread_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_thread_messages",
        null=True,
        blank=True,
        verbose_name="گیرنده رشته خصوصی",
    )
    body = models.TextField(verbose_name="متن پیام")
    is_initial = models.BooleanField(default=False, verbose_name="پیام اولیه")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ارسال")

    class Meta:
        verbose_name = "پیام تیکت"
        verbose_name_plural = "پیام‌های تیکت"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["ticket", "created_at"], name="ticket_msg_ticket_created_idx"
            ),
            models.Index(
                fields=["ticket", "thread_recipient", "created_at"],
                name="ticket_msg_thread_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket"],
                condition=models.Q(is_initial=True),
                name="ticket_one_initial_message",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ticket} - {self.sender}"


class TicketAttachment(models.Model):
    message = models.ForeignKey(
        TicketMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="پیام",
    )
    file = models.FileField(
        upload_to=ticket_attachment_upload_to,
        validators=[
            validate_ticket_file,
            FileExtensionValidator(allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS),
        ],
        verbose_name="فایل",
    )
    original_name = models.CharField(max_length=255, verbose_name="نام اصلی فایل")
    content_type = models.CharField(
        max_length=100, blank=True, verbose_name="نوع محتوا"
    )
    size = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(MAX_ATTACHMENT_SIZE)],
        verbose_name="حجم",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ بارگذاری")

    class Meta:
        verbose_name = "پیوست تیکت"
        verbose_name_plural = "پیوست‌های تیکت"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["message", "created_at"], name="ticket_attach_msg_idx")
        ]

    def __str__(self) -> str:
        return self.original_name

    def clean(self):
        super().clean()
        if self.file:
            validate_ticket_file(self.file)


class TicketAuditEvent(models.Model):
    """Append-only audit trail for ticket operations."""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="audit_events",
        verbose_name="تیکت",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ticket_audit_events",
        null=True,
        blank=True,
        verbose_name="کاربر انجام‌دهنده",
    )
    action = models.CharField(
        max_length=24,
        choices=TicketAuditAction.choices,
        db_index=True,
        verbose_name="عملیات",
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name="جزئیات")
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="تاریخ ثبت"
    )

    class Meta:
        verbose_name = "سابقه تیکت"
        verbose_name_plural = "سوابق تیکت"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["ticket", "-created_at"], name="ticket_audit_ticket_idx"
            ),
            models.Index(
                fields=["actor", "-created_at"], name="ticket_audit_actor_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ticket} / {self.get_action_display()}"
