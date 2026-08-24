from django.contrib import admin
from .models import Property, PropertyAppraisalReport, PropertyImage


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    readonly_fields = ("internal_code",)
    list_display = (
        "title",
        "internal_code",
        "consultant",
        "owner_first_name",
        "owner_last_name",
        "owner_phone",
        "property_type",
        "deal_type",
        "price",
        "status",
        "created_at",
    )
    list_filter = (
        "property_type",
        "deal_type",
        "status",
        "created_at",
    )
    search_fields = (
        "title",
        "internal_code",
        "address",
        "neighborhood",
        "owner_first_name",
        "owner_last_name",
        "owner_phone",
        "consultant__username",
    )
    ordering = ("-created_at",)

    inlines = [PropertyImageInline]


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ["property", "sort_order", "id"]
    list_filter = ["property"]


@admin.register(PropertyAppraisalReport)
class PropertyAppraisalReportAdmin(admin.ModelAdmin):
    list_display = [
        "property",
        "original_filename",
        "file_size",
        "uploaded_by",
        "created_at",
    ]
    search_fields = [
        "property__title",
        "property__internal_code",
        "original_filename",
    ]
    list_filter = ["created_at"]
    ordering = ["-created_at"]
