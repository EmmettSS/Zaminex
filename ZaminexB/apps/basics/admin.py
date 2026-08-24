"""Django-admin registration for the reference data.

A convenience for developers and support staff. The product-facing way to
manage this data is the "اطلاعات پایه" screen backed by the REST API.
"""

from django.contrib import admin

from .models import (
    Attribute,
    City,
    District,
    Province,
    AttributeOption,
    DealType,
    DealTypeAttribute,
    DealTypeSearchAttribute,
    PropertyType,
    PropertyTypeAttribute,
    PropertyTypeSearchAttribute,
    PropertyUsage,
)


class SoftDeleteAdmin(admin.ModelAdmin):
    """Shows soft-deleted rows too, so they can be inspected and restored."""

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.action(description="بازگردانی موارد انتخاب‌شده")
    def restore_selected(self, request, queryset):
        restored = 0
        for obj in queryset:
            if obj.deleted_at is not None:
                obj.restore()
                restored += 1
        self.message_user(request, f"{restored} مورد بازگردانی شد.")

    actions = ["restore_selected"]


class AttributeOptionInline(admin.TabularInline):
    model = AttributeOption
    extra = 0
    fields = ("value", "display_name", "sort_order", "is_active")


class PropertyTypeAttributeInline(admin.TabularInline):
    model = PropertyTypeAttribute
    extra = 0
    autocomplete_fields = ("attribute",)
    fields = ("attribute", "is_required", "sort_order", "is_active")


class PropertyTypeSearchAttributeInline(admin.TabularInline):
    model = PropertyTypeSearchAttribute
    extra = 0
    autocomplete_fields = ("attribute",)
    fields = ("attribute", "sort_order", "is_active")


class DealTypeAttributeInline(admin.TabularInline):
    model = DealTypeAttribute
    extra = 0
    autocomplete_fields = ("attribute",)
    fields = ("attribute", "is_required", "sort_order", "is_active")


class DealTypeSearchAttributeInline(admin.TabularInline):
    model = DealTypeSearchAttribute
    extra = 0
    autocomplete_fields = ("attribute",)
    fields = ("attribute", "sort_order", "is_active")


@admin.register(PropertyUsage)
class PropertyUsageAdmin(SoftDeleteAdmin):
    list_display = ("display_name", "name", "sort_order", "is_active", "deleted_at")
    list_filter = ("is_active",)
    search_fields = ("name", "display_name")
    ordering = ("sort_order",)


@admin.register(PropertyType)
class PropertyTypeAdmin(SoftDeleteAdmin):
    list_display = (
        "display_name", "name", "property_usage", "sort_order", "is_active", "deleted_at",
    )
    list_filter = ("property_usage", "is_active")
    search_fields = ("name", "display_name")
    ordering = ("property_usage", "sort_order")
    inlines = [PropertyTypeAttributeInline, PropertyTypeSearchAttributeInline]


@admin.register(DealType)
class DealTypeAdmin(SoftDeleteAdmin):
    list_display = ("display_name", "name", "sort_order", "is_active", "deleted_at")
    list_filter = ("is_active",)
    search_fields = ("name", "display_name")
    ordering = ("sort_order",)
    inlines = [DealTypeAttributeInline, DealTypeSearchAttributeInline]


@admin.register(Attribute)
class AttributeAdmin(SoftDeleteAdmin):
    list_display = (
        "display_name", "name", "entity", "data_type", "filter_type",
        "is_core", "is_facility", "is_active",
    )
    list_filter = ("entity", "data_type", "is_core", "is_facility", "is_active")
    search_fields = ("name", "display_name")
    ordering = ("entity", "sort_order")
    inlines = [AttributeOptionInline]
    readonly_fields = ("is_core", "core_field")


@admin.register(Province)
class ProvinceAdmin(SoftDeleteAdmin):
    list_display = ("display_name", "name", "sort_order", "is_active", "deleted_at")
    list_filter = ("is_active",)
    search_fields = ("name", "display_name")
    ordering = ("sort_order",)


@admin.register(City)
class CityAdmin(SoftDeleteAdmin):
    list_display = ("display_name", "province", "name", "sort_order", "is_active")
    list_filter = ("province", "is_active")
    search_fields = ("name", "display_name")
    ordering = ("province", "sort_order")
    autocomplete_fields = ("province",)


@admin.register(District)
class DistrictAdmin(SoftDeleteAdmin):
    list_display = ("display_name", "city", "name", "sort_order", "is_active")
    list_filter = ("city__province", "city", "is_active")
    search_fields = ("name", "display_name")
    ordering = ("city", "sort_order")
    autocomplete_fields = ("city",)
