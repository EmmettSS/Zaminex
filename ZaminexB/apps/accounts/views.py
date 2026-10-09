from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import INACTIVE_ACCOUNT_MESSAGE, ZaminexAuthenticationForm
from .models import AdminProfile, ConsultantProfile, LoginMethod, UserRole
from .serializers import AdminProfileSerializer, ConsultantProfileSerializer
from .sms import (
    OtpVerificationError,
    SmsSendError,
    active_login_method,
    find_user_by_mobile,
    is_sms_configured,
    issue_code,
    normalize_mobile,
    otp_length,
    resend_cooldown_remaining,
    send_verification_code,
    set_login_method,
    verify_code,
)
from .throttles import SmsRequestRateThrottle, SmsVerifyRateThrottle


def _safe_next_url(request) -> str:
    """Validate the ``next`` parameter the same way Django's LoginView does.

    The SPA redirects the browser to the returned value after a successful SMS
    login, so an unvalidated ``next`` would be an open-redirect vector.
    """
    next_url = (request.data.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return "/"


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    form_class = ZaminexAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["initial_data"] = {
            "isAuthenticated": False,
            "role": None,
            "userName": "",
            "currentConsultantId": None,
            "initialPage": "login",
            "loginUrl": "/accounts/login/",
            "logoutUrl": "/accounts/logout/",
            "csrfToken": get_token(self.request),
            "next": self.request.GET.get("next", "/"),
            # Which form the login screen shows is decided server-side by the
            # admin's global «گزینه‌های ورود» switch.
            "loginMethod": active_login_method(),
        }

        form = context.get("form")
        login_errors = {}

        if form and form.errors:
            for field, error_list in form.errors.items():
                login_errors[field] = [str(e) for e in error_list]

        # A consultant who was archived mid-session is bounced here by
        # ArchivedConsultantSessionMiddleware with ?deactivated=1.
        if self.request.GET.get("deactivated"):
            login_errors.setdefault("__all__", []).append(INACTIVE_ACCOUNT_MESSAGE)

        context["login_errors"] = login_errors
        return context


class IsAdminRole(BasePermission):
    """DRF permission: only users with the ADMIN role."""

    message = "فقط مدیران به این بخش دسترسی دارند."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", "") == UserRole.ADMIN
        )


class LoginOptionsView(APIView):
    """Admin-only: read/change the active login method (password vs SMS).

    The value is a global singleton, so whatever the admin picks here becomes
    the system's login behaviour immediately (including for the login page).
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        return Response(
            {"method": active_login_method(), "smsConfigured": is_sms_configured()}
        )

    def patch(self, request):
        method = (request.data.get("method") or "").strip()
        if method not in LoginMethod.values:
            return Response(
                {"detail": "روش ورود انتخاب‌شده معتبر نیست."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        set_login_method(method)
        return Response(
            {"method": method, "smsConfigured": is_sms_configured()}
        )


class SmsLoginRequestView(APIView):
    """Anonymous: request an OTP for the given mobile number."""

    permission_classes = [AllowAny]
    throttle_classes = [SmsRequestRateThrottle]

    def post(self, request):
        if active_login_method() != LoginMethod.SMS:
            return Response(
                {"detail": "ورود با کد پیامکی در حال حاضر غیرفعال است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_mobile = (request.data.get("mobile") or "").strip()
        try:
            mobile = normalize_mobile(raw_mobile)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user, _reason = find_user_by_mobile(mobile)
        if user is None:
            # Anti-enumeration: the answer is identical whether or not the
            # number is registered, so the endpoint cannot be used to probe
            # which mobiles have an account.
            return Response(
                {"detail": "در صورت ثبت بودن شماره، کد تأیید برای شما پیامک می‌شود."},
                status=status.HTTP_200_OK,
            )

        cooldown = resend_cooldown_remaining(mobile)
        if cooldown > 0:
            return Response(
                {"detail": f"ارسال کد به‌تازگی انجام شده است. {cooldown} ثانیه دیگر صبر کنید."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            code = issue_code(mobile)
            send_verification_code(mobile, code)
        except SmsSendError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {"detail": "کد تأیید برای شماره شما پیامک شد."},
            status=status.HTTP_200_OK,
        )


class SmsLoginVerifyView(APIView):
    """Anonymous: verify an OTP and start an authenticated session."""

    permission_classes = [AllowAny]
    throttle_classes = [SmsVerifyRateThrottle]

    def post(self, request):
        if active_login_method() != LoginMethod.SMS:
            return Response(
                {"detail": "ورود با کد پیامکی در حال حاضر غیرفعال است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_mobile = (request.data.get("mobile") or "").strip()
        code = (request.data.get("code") or "").strip()
        try:
            mobile = normalize_mobile(raw_mobile)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not code.isdigit() or len(code) != otp_length():
            return Response(
                {"detail": "کد تأیید واردشده صحیح نیست."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = verify_code(mobile, code)
        except OtpVerificationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # django.contrib.auth.login() already rotates the session key for a
        # fresh anonymous session, which defeats session fixation.
        login(request, user)
        return Response(
            {"detail": "ورود با موفقیت انجام شد.", "next": _safe_next_url(request)},
            status=status.HTTP_200_OK,
        )


def change_password_for_user(request) -> Response:
    """Shared password-change logic for the authenticated user (any role)."""
    user = request.user
    current_password = request.data.get("current_password") or request.data.get("currentPassword")
    new_password = request.data.get("new_password") or request.data.get("newPassword")

    if not current_password or not new_password:
        return Response(
            {"detail": "وارد کردن رمز عبور فعلی و رمز عبور جدید الزامی است."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not user.check_password(current_password):
        return Response(
            {"detail": "رمز عبور فعلی نامعتبر است."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(new_password) < 8:
        return Response(
            {"detail": "رمز عبور جدید باید حداقل ۸ کاراکتر باشد."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new_password)
    user.save()
    update_session_auth_hash(request, user)
    from apps.common.session_security import flush_user_sessions

    flush_user_sessions(user, keep_session_key=request.session.session_key)

    return Response({"detail": "رمز عبور با موفقیت تغییر کرد."}, status=status.HTTP_200_OK)


class ConsultantProfileViewSet(viewsets.ModelViewSet):
    """Full CRUD for ConsultantProfile.

    The queryset only ever contains real consultants (users with the AGENT
    role) so admin accounts never show up in the admin dashboard's
    consultant list, comboboxes or analytics.

    Creating a consultant also creates the linked User account.
    Updating a consultant can update both the profile fields and
    the linked User fields (first_name, last_name, email).
    Archive is done via PATCH {is_active: false}.
    Delete removes the consultant *completely* from the backend
    (profile + user account + owned data).
    """

    serializer_class = ConsultantProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            ConsultantProfile.objects.select_related("user")
            .filter(user__role=UserRole.AGENT)
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["is_admin_request"] = (
            getattr(self.request.user, "role", "") == UserRole.ADMIN
        )
        return context

    def create(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") != UserRole.ADMIN:
            return Response(
                {"detail": "فقط مدیر می‌تواند مشاور جدید اضافه کند."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if getattr(request.user, "role", "") != UserRole.ADMIN and instance.user != request.user:
            return Response(
                {"detail": "شما اجازه ویرایش این پروفایل را ندارید."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") != UserRole.ADMIN:
            return Response(
                {"detail": "فقط مدیر می‌تواند مشاور را حذف کند."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """Archive the consultant instead of hard-deleting data.

        A hard delete destroys the audit trail (ActivityLog rows point to the
        user via a SET_NULL foreign key), removes every property the consultant
        ever created and permanently deletes the login account. The UI already
        models deactivation as *archive* (is_active=False), so we keep that
        semantic here: the consultant is locked out by ArchivedConsultant
        SessionMiddleware, their profile is hidden from lists, but the history
        remains reportable.
        """
        with transaction.atomic():
            instance = ConsultantProfile.objects.select_for_update().get(pk=instance.pk)
            instance.is_active = False
            instance.save(update_fields=["is_active"])
            user = instance.user
            user.is_active = False
            user.save(update_fields=["is_active"])

            # Immediately terminate every remaining session for this user so a
            # stolen cookie cannot survive the archive action.
            from apps.common.session_security import flush_user_sessions
            flush_user_sessions(user)

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        # Admins have their own dedicated profile endpoint (/accounts/admins/me/).
        # Blocking them here also prevents admin accounts from accidentally
        # creating a ConsultantProfile and appearing in the consultant list.
        if getattr(request.user, "role", "") == UserRole.ADMIN:
            return Response(
                {"detail": "مدیران از طریق endpoint اختصاصی خود پروفایلشان را مدیریت می‌کنند."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            profile = request.user.consultant_profile
        except AttributeError:
            profile, _ = ConsultantProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    "full_name": request.user.get_full_name() or request.user.username,
                    "mobile": None,
                    "branch": "شعبه مرکزی",
                }
            )

        if request.method == "GET":
            serializer = self.get_serializer(profile)
            return Response(serializer.data)

        elif request.method == "PATCH":
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        return change_password_for_user(request)

    @action(detail=False, methods=["post"], url_path="me/change-password")
    def change_password_me(self, request):
        return change_password_for_user(request)


class AdminProfileViewSet(viewsets.GenericViewSet):
    """"My Profile" for the logged-in ADMIN.

    Exposes exactly the same data shape as the consultant profile API
    (GET/PATCH on ``me`` + change-password) so the admin panel can reuse the
    consultant "My Profile" UI one-to-one, while keeping admin data in a
    separate AdminProfile model — admins never pollute the consultant list.
    """

    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return AdminProfile.objects.select_related("user").filter(
            user__role=UserRole.ADMIN
        )

    def _get_or_create_profile(self, user):
        profile = AdminProfile.objects.filter(user=user).first()
        if profile is None:
            profile = AdminProfile.objects.create(
                user=user,
                full_name=user.get_full_name() or user.username,
                branch="شعبه مرکزی",
            )
        return profile

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        profile = self._get_or_create_profile(request.user)

        if request.method == "GET":
            serializer = self.get_serializer(profile)
            return Response(serializer.data)

        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        return change_password_for_user(request)

    @action(detail=False, methods=["post"], url_path="me/change-password")
    def change_password_me(self, request):
        return change_password_for_user(request)
