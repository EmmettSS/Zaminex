from django.contrib import admin

from .models import (
    Ticket,
    TicketAttachment,
    TicketAuditEvent,
    TicketMessage,
    TicketParticipant,
)


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    fields = ("sender", "thread_recipient", "body", "is_initial", "created_at")
    readonly_fields = fields
    can_delete = False
    ordering = ("created_at", "id")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class TicketParticipantInline(admin.TabularInline):
    model = TicketParticipant
    extra = 0
    fields = ("user", "role", "is_read", "read_at", "last_visible_message_at")
    readonly_fields = ("created_at",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number",
        "title",
        "ticket_type",
        "subject_type",
        "status",
        "priority",
        "created_by",
        "reply_count",
        "sla_due_at",
        "updated_at",
    )
    list_filter = ("ticket_type", "subject_type", "status", "priority", "created_at")
    search_fields = (
        "ticket_number",
        "title",
        "created_by__username",
        "created_by__first_name",
        "created_by__last_name",
    )
    readonly_fields = (
        "ticket_number",
        "reply_count",
        "last_message_at",
        "last_message_sender",
        "created_at",
        "updated_at",
    )
    inlines = (TicketParticipantInline, TicketMessageInline)
    ordering = ("-updated_at", "-id")


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "sender", "thread_recipient", "is_initial", "created_at")
    search_fields = ("ticket__ticket_number", "body", "sender__username")
    list_filter = ("is_initial", "created_at")
    readonly_fields = (
        "ticket",
        "sender",
        "thread_recipient",
        "body",
        "is_initial",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketParticipant)
class TicketParticipantAdmin(admin.ModelAdmin):
    list_display = ("ticket", "user", "role", "is_read", "last_visible_message_at")
    list_filter = ("role", "is_read")
    search_fields = (
        "ticket__ticket_number",
        "user__username",
        "user__first_name",
        "user__last_name",
    )


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "message", "content_type", "size", "created_at")
    search_fields = ("original_name", "message__ticket__ticket_number")
    readonly_fields = ("created_at",)


@admin.register(TicketAuditEvent)
class TicketAuditEventAdmin(admin.ModelAdmin):
    list_display = ("ticket", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("ticket__ticket_number", "actor__username")
    readonly_fields = ("ticket", "actor", "action", "metadata", "created_at")
