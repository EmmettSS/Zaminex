import types

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import ZaminexAdminAuthenticationForm
from .models import ConsultantProfile, LoginAttempt, User, UserRole


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
