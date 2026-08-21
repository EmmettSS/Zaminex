from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from .forms import INACTIVE_ACCOUNT_MESSAGE, ZaminexAuthenticationForm
from .models import AdminProfile, ConsultantProfile, UserRole
from .serializers import AdminProfileSerializer, ConsultantProfileSerializer


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
