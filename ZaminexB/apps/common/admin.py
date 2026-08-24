from django.contrib import admin
from .models import District, CompanySettings, ActivityLog


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['name']
    ordering = ['name']
    list_editable = ['is_active']


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'email', 'phone', 'ai_enabled', 'updated_at']
    fieldsets = (
        (
            "اطلاعات شرکت",
            {"fields": ("company_name", "license_number", "email", "phone", "address")},
        ),
        (
            "هوش مصنوعی (API)",
            {
                "fields": (
                    "ai_enabled",
                    "ai_api_base_url",
                    "ai_api_key",
                    "ai_model",
                ),
                "description": (
                    "تنظیمات سرویس هوش مصنوعی برای «توصیف هوش مصنوعی» مشاور و ملک. "
                    "آدرس پایه باید با قالب OpenAI (chat/completions) سازگار باشد. "
                    "نام مدل الزامی است."
                ),
            },
        ),
    )


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'target_type', 'description', 'created_at']
    list_filter = ['action', 'target_type', 'created_at']
    search_fields = ['description', 'user__username']
    ordering = ['-created_at']
