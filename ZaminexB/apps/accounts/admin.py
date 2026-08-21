import types

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import ZaminexAdminAuthenticationForm
from .models import (
    ConsultantProfile,
    LoginAttempt,
    LoginSettings,
    SmsLoginCode,
    SmsProviderSettings,
    User,
    UserRole,
)


def _admin_has_permission(self, request):
    user = getattr(request, "user", None)
    return bool(
        user
        and user.is_active
        and user.is_staff
        and getattr(user, "role", "") == UserRole.ADMIN
    )


admin.site.login_form = ZaminexAdminAuthenticationForm
admin.site.has_permission = types.MethodType(_admin_has_permission, admin.site)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("نقش کاربری", {"fields": ("role",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active", "groups")


@admin.register(ConsultantProfile)
class ConsultantProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "mobile", "branch", "is_active", "hired_at", "user")
    list_filter = ("is_active", "branch")
    search_fields = ("full_name", "mobile", "branch", "user__username")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("username", "failed_attempts", "locked_until", "last_failed_at", "last_ip")
    search_fields = ("username", "last_ip")
    list_filter = ("locked_until",)
    readonly_fields = ("updated_at",)


class SmsProviderSettingsForm(forms.ModelForm):
    """Never echo the stored secrets back into the admin form.

    The API keys are encrypted at rest; showing the ciphertext in the field is
    both confusing and pointless. The fields therefore render empty and are
    only overwritten when a new value is typed.
    """

    class Meta:
        model = SmsProviderSettings
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ("smsir_api_key", "kavenegar_api_key"):
            self.fields[field].required = False
            if self.instance and getattr(self.instance, field):
                self.fields[field].widget.attrs["placeholder"] = (
                    "تنظیم شده است — برای تغییر، مقدار جدید را وارد کنید"
                )
            self.initial[field] = ""

    def clean(self):
        cleaned = super().clean()
        if self.instance and self.instance.pk:
            # Empty means "keep the existing key" rather than "delete it".
            for field in ("smsir_api_key", "kavenegar_api_key"):
                if not cleaned.get(field):
                    cleaned[field] = getattr(self.instance, field)
        return cleaned


@admin.register(SmsProviderSettings)
class SmsProviderSettingsAdmin(admin.ModelAdmin):
    form = SmsProviderSettingsForm
    list_display = ("updated_at",)
    readonly_fields = ("updated_at",)
    fieldsets = (
        (
            "سرویس اصلی — sms.ir",
            {
                "fields": ("smsir_api_key", "smsir_line_number", "smsir_template_id"),
                "description": (
                    "کلید API، شماره خط (در صورت نیاز) و شناسهٔ قالب «تأیید» از پنل sms.ir. "
                    "کد تأیید در پارامتر PARAMETER1 قالب قرار می‌گیرد."
                ),
            },
        ),
        (
            "سرویس پشتیبان — کاوه‌نگار",
            {
                "fields": (
                    "kavenegar_api_key",
                    "kavenegar_sender",
                    "kavenegar_template_name",
                    "kavenegar_message",
                ),
                "description": (
                    "اگر ارسال از طریق sms.ir ناموفق باشد، پیامک به‌صورت خودکار از کاوه‌نگار ارسال می‌شود. "
                    "در صورت تنظیم «نام قالب احراز هویت» از قالب lookup استفاده می‌شود؛ وگرنه متن سادهٔ بالا "
                    "(که {code} در آن با کد تأیید جایگزین می‌شود) ارسال خواهد شد."
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not SmsProviderSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoginSettings)
class LoginSettingsAdmin(admin.ModelAdmin):
    list_display = ("method", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not LoginSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SmsLoginCode)
class SmsLoginCodeAdmin(admin.ModelAdmin):
    list_display = ("mobile", "created_at", "expires_at", "attempts", "consumed_at")
    search_fields = ("mobile",)
    list_filter = ("consumed_at",)
    readonly_fields = ("mobile", "code_hash", "created_at", "expires_at", "attempts", "consumed_at")
