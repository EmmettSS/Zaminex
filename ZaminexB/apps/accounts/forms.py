from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .login_security import (
    format_lockout_message,
    get_active_lock,
    record_failed_login,
    reset_login_attempts,
)
from .models import UserRole

User = get_user_model()

# Shown on the login page when an archived (deactivated) consultant
# tries to log in, and when the session middleware bounces them out.
INACTIVE_ACCOUNT_MESSAGE = (
    "حساب کاربری شما غیرفعال شده است. برای اطلاع از دلیل آن و بازیابی دسترسی، "
    "با مدیریت مجموعه تماس بگیرید."
)
INVALID_LOGIN_MESSAGE = "نام کاربری یا رمز عبور واردشده صحیح نیست."


class ZaminexAuthenticationForm(AuthenticationForm):
    """Login form with Persian errors, consultant activation checks and lockout.

    Five failed password checks for the same normalized username within the
    configured window temporarily block login with that username. The lock is
    account-scoped (not only IP-scoped), is persisted in the database, and is
    cleared after a successful login.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": INVALID_LOGIN_MESSAGE,
        "inactive": "این حساب کاربری غیرفعال است.",
        "inactive_account": INACTIVE_ACCOUNT_MESSAGE,
        "too_many_attempts": "تعداد تلاش‌های ناموفق بیش از حد مجاز است.",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        self.fields["username"].label = "نام کاربری"
        self.fields["password"].label = "رمز عبور"
        self.fields["username"].error_messages.update(
            {"required": "وارد کردن نام کاربری الزامی است."}
        )
        self.fields["password"].error_messages.update(
            {"required": "وارد کردن رمز عبور الزامی است."}
        )

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if not username or not password:
            return super().clean()

        locked_until = get_active_lock(username)
        if locked_until:
            raise ValidationError(
                format_lockout_message(locked_until),
                code="too_many_attempts",
            )

        try:
            cleaned_data = super().clean()
        except ValidationError as exc:
            if self._has_error_code(exc, "invalid_login"):
                locked_until = record_failed_login(username, request=self.request)
                if locked_until:
                    raise ValidationError(
                        format_lockout_message(locked_until),
                        code="too_many_attempts",
                    )
            raise

        user = self.get_user()
        if user is not None and getattr(user, "role", "") == UserRole.AGENT:
            profile = getattr(user, "consultant_profile", None)
            if profile is not None and not profile.is_active:
                raise ValidationError(
                    self.error_messages["inactive_account"],
                    code="inactive_account",
                )

        reset_login_attempts(username)
        return cleaned_data

    @staticmethod
    def _has_error_code(exc: ValidationError, code: str) -> bool:
        if getattr(exc, "code", None) == code:
            return True
        for error in getattr(exc, "error_list", []) or []:
            if getattr(error, "code", None) == code:
                return True
        for errors in getattr(exc, "error_dict", {}).values():
            for error in errors:
                if getattr(error, "code", None) == code:
                    return True
        return False


class ZaminexAdminAuthenticationForm(ZaminexAuthenticationForm):
    """Django admin login: same lockout, and only ADMIN staff may enter."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff or getattr(user, "role", "") != UserRole.ADMIN:
            raise ValidationError(
                "شما اجازه ورود به پنل مدیریت را ندارید.",
                code="invalid_login",
            )
