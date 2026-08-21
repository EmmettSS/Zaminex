from django.contrib import admin
from .models import Property, PropertyImage


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "internal_code",
        "consultant",
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
        "consultant__username",
    )
    ordering = ("-created_at",)

    inlines = [PropertyImageInline]


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ["property", "sort_order", "id"]
    list_filter = ["property"]
