from django.contrib import admin

from .models import FollowUp


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "follow_up_type",
        "status",
        "consultant",
        "consultant_name",
        "property",
        "property_title",
        "scheduled_at",
        "is_archived",
    )
    list_filter = ("follow_up_type", "status", "is_archived", "scheduled_at")
    search_fields = (
        "title",
        "contact_name",
        "consultant__username",
        "consultant_name",
        "property__title",
        "property_title",
        "notes",
        "outcome",
    )
    ordering = ("scheduled_at", "-created_at")
    readonly_fields = ("created_at", "updated_at", "archived_at")
