from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import ConsultantProfile, LoginAttempt, UserRole

User = get_user_model()


class ConsultantProfileViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testagent",
            email="agent@example.com",
            password="oldpassword123",
            first_name="Ali",
            last_name="Rezaei",
            role=UserRole.AGENT,
        )
        self.profile = ConsultantProfile.objects.create(
            user=self.user,
            full_name="Ali Rezaei",
            mobile="09123456789",
            branch="شعبه مرکزی",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_me(self):
        url = reverse("accounts:consultant-me")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["full_name"], "Ali Rezaei")
        self.assertEqual(res.data["user"]["email"], "agent@example.com")

    def test_patch_me(self):
        url = reverse("accounts:consultant-me")
        payload = {
            "first_name": "Hassan",
            "last_name": "Tehrani",
            "full_name": "Hassan Tehrani",
            "mobile": "09111111111",
            "branch": "شعبه میدان ساعت",
            "notes": "مشاور ارشد ملکی",
        }
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Hassan Tehrani")
        self.assertEqual(self.profile.mobile, "09111111111")
        self.assertEqual(self.profile.branch, "شعبه میدان ساعت")
        self.assertEqual(self.profile.notes, "مشاور ارشد ملکی")
        self.assertEqual(self.user.first_name, "Hassan")
        self.assertEqual(self.user.last_name, "Tehrani")

    def test_change_password(self):
        url = reverse("accounts:consultant-change-password")
        payload = {
            "current_password": "oldpassword123",
            "new_password": "newpassword456",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpassword456"))

    def test_change_password_invalid_current(self):
        url = reverse("accounts:consultant-change-password")
        payload = {
            "current_password": "wrongpassword",
            "new_password": "newpassword456",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_permission_update_other_consultant(self):
        other_user = User.objects.create_user(
            username="otheragent",
            password="password",
            role=UserRole.AGENT,
        )
        other_profile = ConsultantProfile.objects.create(
            user=other_user,
            full_name="Other Agent",
            mobile="09222222222",
            branch="شعبه مرکزی",
        )
        url = reverse("accounts:consultant-detail", args=[other_profile.id])
        res = self.client.patch(url, {"full_name": "Hacked Name"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


# =============================================================================
#  Tests for the admin-dashboard / deletion / archive-login fixes
# =============================================================================

from django.test import Client
from django.utils import timezone

from apps.accounts.forms import INACTIVE_ACCOUNT_MESSAGE
from apps.accounts.models import AdminProfile
from apps.followups.models import FollowUp
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task


class ConsultantListAdminVisibilityTests(TestCase):
    """Fix #1: admin accounts must never appear in the consultant list."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="paneladmin", password="adminpass123", role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="panelagent", password="agentpass123", role=UserRole.AGENT
        )
        self.agent_profile = ConsultantProfile.objects.create(
            user=self.agent, full_name="Agent One", branch="شعبه مرکزی"
        )
        # Legacy pollution: an admin that somehow got a ConsultantProfile row.
        self.admin_profile = ConsultantProfile.objects.create(
            user=self.admin, full_name="Admin With Profile", branch="شعبه مرکزی"
        )
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.admin)

    def test_list_only_returns_agents(self):
        res = self.client_api.get(reverse("accounts:consultant-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        usernames = {row["user"]["username"] for row in res.data}
        self.assertIn("panelagent", usernames)
        self.assertNotIn("paneladmin", usernames)

    def test_detail_of_admin_profile_is_404(self):
        res = self.client_api.get(
            reverse("accounts:consultant-detail", args=[self.admin_profile.id])
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_consultant_me_forbidden_for_admin(self):
        res = self.client_api.get(reverse("accounts:consultant-me"))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        # No new profile should have been created for the admin either.
        self.assertEqual(
            ConsultantProfile.objects.filter(user=self.admin).count(), 1
        )

    def test_analytics_exclude_admin_profiles(self):
        res = self.client_api.get("/common/api/analytics/consultants/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        names = {row["fullName"] for row in res.data["consultants"]}
        self.assertIn("Agent One", names)
        self.assertNotIn("Admin With Profile", names)


class AdminProfileApiTests(TestCase):
    """Fix #2: the admin's own profile API (My Profile in the admin panel)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="bossadmin",
            password="adminpass123",
            role=UserRole.ADMIN,
            first_name="Boss",
            last_name="Admin",
        )
        self.agent = User.objects.create_user(
            username="regularagent", password="agentpass123", role=UserRole.AGENT
        )
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.admin)

    def test_get_me_auto_creates_admin_profile(self):
        res = self.client_api.get("/accounts/admins/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["user"]["username"], "bossadmin")
        self.assertEqual(res.data["user"]["role"], UserRole.ADMIN)
        self.assertEqual(res.data["full_name"], "Boss Admin")
        for key in ("id", "mobile", "branch", "profile_image", "hired_at", "notes", "is_active"):
            self.assertIn(key, res.data)
        self.assertTrue(AdminProfile.objects.filter(user=self.admin).exists())

    def test_patch_me_updates_admin_profile_and_user(self):
        self.client_api.get("/accounts/admins/me/")  # ensure profile exists
        payload = {
            "first_name": "بزرگ",
            "last_name": "مدیر",
            "full_name": "بزرگ مدیر",
            "email": "boss@zaminex.ir",
            "mobile": "09131234567",
            "branch": "شعبه مرکزی",
            "notes": "مدیر مجموعه",
        }
        res = self.client_api.patch("/accounts/admins/me/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        profile = self.admin.admin_profile
        self.assertEqual(profile.full_name, "بزرگ مدیر")
        self.assertEqual(profile.mobile, "09131234567")
        self.assertEqual(profile.notes, "مدیر مجموعه")
        self.assertEqual(self.admin.first_name, "بزرگ")
        self.assertEqual(self.admin.email, "boss@zaminex.ir")

    def test_patch_me_rejects_invalid_mobile(self):
        self.client_api.get("/accounts/admins/me/")
        res = self.client_api.patch(
            "/accounts/admins/me/", {"mobile": "123"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password(self):
        res = self.client_api.post(
            "/accounts/admins/change-password/",
            {"current_password": "adminpass123", "new_password": "newadminpass456"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("newadminpass456"))

    def test_agent_cannot_access_admin_profile_api(self):
        self.client_api.force_authenticate(user=self.agent)
        self.assertEqual(self.client_api.get("/accounts/admins/me/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client_api.post(
                "/accounts/admins/change-password/",
                {"current_password": "x", "new_password": "y"},
                format="json",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )


class ConsultantFullDeletionTests(TestCase):
    """Fix #3: deleting a consultant must remove it completely from the backend."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="deleteadmin", password="adminpass123", role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="deleteagent", password="agentpass123", role=UserRole.AGENT
        )
        self.profile = ConsultantProfile.objects.create(
            user=self.agent, full_name="Delete Me", branch="شعبه مرکزی"
        )
        # Related data covering every FK type, including all PROTECT ones.
        self.property = Property.objects.create(
            title="P", internal_code="DEL-1", consultant=self.agent,
            property_type="APARTMENT", deal_type="SALE", price=1000, area=50,
            address="a", neighborhood="n",
        )
        self.listing = Listing.objects.create(
            property=self.property, title="L", publish_channel="WEBSITE",
            created_by=self.agent, assigned_to=self.agent,
        )
        self.task = Task.objects.create(
            title="T", created_by=self.agent, assigned_to=self.agent,
            due_date=timezone.now().date(),
        )
        self.followup = FollowUp.objects.create(
            title="F", contact_name="C", consultant=self.agent, property=self.property,
        )
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.admin)

    def test_delete_archives_consultant_instead_of_hard_deleting(self):
        url = reverse("accounts:consultant-detail", args=[self.profile.id])
        res = self.client_api.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # Security: deleting a consultant must be an archive, not a hard
        # delete, so the audit trail stays intact and data is not destroyed
        # by a mistaken click.
        self.profile.refresh_from_db()
        self.agent.refresh_from_db()
        self.assertFalse(self.profile.is_active)
        self.assertFalse(self.agent.is_active)
        self.assertTrue(Property.objects.filter(pk=self.property.pk).exists())
        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertTrue(FollowUp.objects.filter(pk=self.followup.pk).exists())

    def test_delete_keeps_other_consultants_data(self):
        other = User.objects.create_user(
            username="survivor", password="agentpass123", role=UserRole.AGENT
        )
        other_profile = ConsultantProfile.objects.create(
            user=other, full_name="Survivor", branch="شعبه مرکزی"
        )
        other_task = Task.objects.create(
            title="Other", created_by=other, assigned_to=self.agent,
            due_date=timezone.now().date(),
        )
        res = self.client_api.delete(
            reverse("accounts:consultant-detail", args=[self.profile.id])
        )
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(ConsultantProfile.objects.filter(pk=other_profile.pk).exists())
        other_task.refresh_from_db()
        # Archiving a consultant must not touch other consultants' tasks.
        self.assertEqual(other_task.assigned_to_id, self.agent.id)

    def test_non_admin_cannot_delete_consultant(self):
        outsider = User.objects.create_user(
            username="outsider", password="agentpass123", role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=outsider, full_name="Outsider", branch="شعبه مرکزی"
        )
        self.client_api.force_authenticate(user=outsider)
        res = self.client_api.delete(
            reverse("accounts:consultant-detail", args=[self.profile.id])
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=self.agent.pk).exists())

    def test_non_admin_cannot_create_consultant(self):
        outsider = User.objects.create_user(
            username="outsider2", password="agentpass123", role=UserRole.AGENT
        )
        self.client_api.force_authenticate(user=outsider)
        res = self.client_api.post(
            reverse("accounts:consultant-list"),
            {
                "first_name": "X", "last_name": "Y", "username": "newguy",
                "password": "password123", "full_name": "X Y",
                "mobile": "09141112233", "branch": "شعبه مرکزی",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_consultant_cannot_self_archive(self):
        self.client_api.force_authenticate(user=self.agent)
        res = self.client_api.patch(
            reverse("accounts:consultant-me"), {"is_active": False}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_active)


def extract_login_errors(html: str) -> dict:
    """Pull the login-errors JSON payload rendered into the login page."""
    import json
    import re

    match = re.search(r'id="login-errors"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except ValueError:
        return {}


class ArchivedConsultantLoginTests(TestCase):
    """Fix #4: archived consultants cannot log in and see a clear message."""

    def setUp(self):
        self.agent = User.objects.create_user(
            username="archivedagent", password="agentpass123", role=UserRole.AGENT
        )
        self.profile = ConsultantProfile.objects.create(
            user=self.agent, full_name="Archived Agent", branch="شعبه مرکزی",
            is_active=True,
        )
        self.admin = User.objects.create_user(
            username="loginadmin", password="adminpass123", role=UserRole.ADMIN
        )

    def _login(self, username, password):
        return Client().post(
            "/accounts/login/", {"username": username, "password": password}
        )

    def test_active_consultant_can_login(self):
        res = self._login("archivedagent", "agentpass123")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res["Location"], "/")

    def test_archived_consultant_is_rejected_with_message(self):
        self.profile.is_active = False
        self.profile.save()
        res = self._login("archivedagent", "agentpass123")
        self.assertEqual(res.status_code, 200)  # re-rendered login page
        errors = extract_login_errors(res.content.decode("utf-8"))
        self.assertIn(INACTIVE_ACCOUNT_MESSAGE, errors.get("__all__", []))

    def test_admin_login_unaffected(self):
        res = self._login("loginadmin", "adminpass123")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res["Location"], "/")

    def test_reactivated_consultant_can_login_again(self):
        self.profile.is_active = False
        self.profile.save()
        self.assertEqual(self._login("archivedagent", "agentpass123").status_code, 200)
        self.profile.is_active = True
        self.profile.save()
        res = self._login("archivedagent", "agentpass123")
        self.assertEqual(res.status_code, 302)

    def test_mid_session_archiving_logs_consultant_out(self):
        web = Client()
        self.assertTrue(web.login(username="archivedagent", password="agentpass123"))
        self.assertEqual(web.get("/").status_code, 200)

        self.profile.is_active = False
        self.profile.save()

        res = web.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("deactivated=1", res["Location"])

        res = web.get("/accounts/login/?deactivated=1")
        errors = extract_login_errors(res.content.decode("utf-8"))
        self.assertIn(INACTIVE_ACCOUNT_MESSAGE, errors.get("__all__", []))
        self.assertNotIn("_auth_user_id", web.session)

    def test_wrong_password_still_shows_normal_error(self):
        res = self._login("archivedagent", "wrongpassword")
        self.assertEqual(res.status_code, 200)
        errors = extract_login_errors(res.content.decode("utf-8"))
        self.assertNotIn(INACTIVE_ACCOUNT_MESSAGE, errors.get("__all__", []))
        self.assertTrue(errors.get("__all__"))  # generic invalid-login error


@override_settings(LOGIN_FAILURE_LIMIT=5, LOGIN_LOCKOUT_SECONDS=600, LOGIN_FAILURE_WINDOW_SECONDS=900)
class LoginAttemptLockoutTests(TestCase):
    """Login should be temporarily blocked after repeated failed attempts."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="limitedagent", password="agentpass123", role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=self.user, full_name="Limited Agent", branch="شعبه مرکزی", is_active=True
        )

    def _login(self, username="limitedagent", password="wrongpass"):
        return Client().post(
            "/accounts/login/", {"username": username, "password": password}
        )

    def test_username_is_locked_after_five_failed_attempts(self):
        for _ in range(4):
            res = self._login()
            self.assertEqual(res.status_code, 200)
            errors = extract_login_errors(res.content.decode("utf-8"))
            self.assertIn("نام کاربری یا رمز عبور واردشده صحیح نیست.", errors.get("__all__", []))

        res = self._login()
        self.assertEqual(res.status_code, 200)
        errors = extract_login_errors(res.content.decode("utf-8"))
        self.assertTrue(any("مسدود" in msg for msg in errors.get("__all__", [])))

        attempt = LoginAttempt.objects.get(username="limitedagent")
        self.assertIsNotNone(attempt.locked_until)
        self.assertEqual(attempt.failed_attempts, 5)

        res = self._login(password="agentpass123")
        self.assertEqual(res.status_code, 200)
        errors = extract_login_errors(res.content.decode("utf-8"))
        self.assertTrue(any("مسدود" in msg for msg in errors.get("__all__", [])))

    def test_successful_login_clears_previous_failed_attempts(self):
        self._login()
        self._login()
        self.assertEqual(LoginAttempt.objects.get(username="limitedagent").failed_attempts, 2)

        res = self._login(password="agentpass123")
        self.assertEqual(res.status_code, 302)
        self.assertFalse(LoginAttempt.objects.filter(username="limitedagent").exists())

    def test_expired_lock_allows_login_again(self):
        for _ in range(5):
            self._login()

        from django.utils import timezone

        attempt = LoginAttempt.objects.get(username="limitedagent")
        attempt.locked_until = timezone.now() - timezone.timedelta(seconds=1)
        attempt.save(update_fields=["locked_until", "updated_at"])

        res = self._login(password="agentpass123")
        self.assertEqual(res.status_code, 302)
        self.assertFalse(LoginAttempt.objects.filter(username="limitedagent").exists())


class LogoutFlowTests(TestCase):
    """Logout is the SPA's only POST navigation, so it must keep working with
    every token source the frontend legitimately uses (the raw csrftoken
    cookie secret and the server-rendered masked page token) while staying a
    CSRF-protected POST.

    These tests mirror the browser flow 1:1 with CSRF enforcement enabled:
      - the login page renders `csrfToken` (masked) into `initial-data`,
      - the logout handler refreshes the cookie through a CSRF-issuing GET
        and then POSTs the token read from the cookie,
      - a missing cookie/token must never silently log the user out.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="logoutuser",
            password="logoutpass123",
            role=UserRole.AGENT,
        )
        ConsultantProfile.objects.create(
            user=self.user, full_name="Logout User", branch="شعبه مرکزی"
        )

    @staticmethod
    def _page_csrf_token(response):
        import json
        import re

        match = re.search(
            r'<script id="initial-data" type="application/json">(.*?)</script>',
            response.content.decode("utf-8"),
            re.S,
        )
        assert match, "initial-data script not found in the page"
        return json.loads(match.group(1))["csrfToken"]

    def _logged_in_client(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(reverse("accounts:login"))
        token = self._page_csrf_token(page)
        res = client.post(
            reverse("accounts:login"),
            {
                "username": "logoutuser",
                "password": "logoutpass123",
                "csrfmiddlewaretoken": token,
            },
        )
        assert res.status_code == 302, "login must succeed in test setup"
        return client

    def test_logout_requires_post(self):
        client = self._logged_in_client()
        res = client.get(reverse("accounts:logout"))
        self.assertEqual(res.status_code, 405)

    def test_logout_rejects_missing_csrf(self):
        client = self._logged_in_client()
        client.cookies.pop("csrftoken", None)
        res = client.post(reverse("accounts:logout"), {})
        self.assertEqual(res.status_code, 403)
        # The session must survive a failed logout attempt: the user is still
        # served the authenticated dashboard.
        self.assertEqual(client.get("/").status_code, 200)

    def test_logout_with_cookie_token_succeeds(self):
        """The JS reads the raw cookie secret and posts it — must be accepted."""
        client = self._logged_in_client()
        cookie_token = client.cookies.get("csrftoken").value
        res = client.post(
            reverse("accounts:logout"), {"csrfmiddlewaretoken": cookie_token}
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res["Location"], reverse("accounts:login"))
        # The server-side session is actually destroyed.
        follow = client.get("/")
        self.assertEqual(follow.status_code, 302)
        self.assertTrue(follow["Location"].startswith(reverse("accounts:login")))

    def test_logout_with_server_rendered_page_token_succeeds(self):
        """The masked token rendered into `initial-data` must also be accepted."""
        client = self._logged_in_client()
        dash = client.get("/")
        page_token = self._page_csrf_token(dash)
        res = client.post(
            reverse("accounts:logout"), {"csrfmiddlewaretoken": page_token}
        )
        self.assertEqual(res.status_code, 302)

    def test_logout_after_cookie_refresh_succeeds(self):
        """Broken browser state (csrftoken cookie lost): the frontend now
        refreshes the cookie through a CSRF-issuing GET before posting, and
        the subsequent logout succeeds instead of returning a raw 403."""
        client = self._logged_in_client()
        client.cookies.pop("csrftoken", None)
        # Step 1 of the new frontend flow: refresh the cookie.
        client.get(reverse("accounts:login"))
        fresh_token = client.cookies.get("csrftoken").value
        # Step 2: POST it like every other API call.
        res = client.post(
            reverse("accounts:logout"), {"csrfmiddlewaretoken": fresh_token}
        )
        self.assertEqual(res.status_code, 302)

    def test_logout_still_rejects_wrong_token(self):
        """A forged token with a valid cookie must be rejected (no CSRF hole)."""
        client = self._logged_in_client()
        res = client.post(
            reverse("accounts:logout"),
            {"csrfmiddlewaretoken": "x" * 32},
        )
        self.assertEqual(res.status_code, 403)


# =============================================================================
#  SMS OTP login (اصلاحیه دوم): request/verify flow, fallback, method switch
# =============================================================================

from datetime import timedelta
from unittest import mock

from django.core.cache import cache

from apps.accounts import sms
from apps.accounts.forms import (
    SMS_LOGIN_REQUIRED_MESSAGE,
    ZaminexAdminAuthenticationForm,
)
from apps.accounts.models import (
    LoginMethod,
    LoginSettings,
    SmsLoginCode,
    SmsProviderSettings,
)
from apps.accounts.sms import (
    SmsSendError,
    normalize_mobile,
    set_login_method,
)


class MobileNormalizationTests(TestCase):
    def test_accepts_standard_forms(self):
        self.assertEqual(normalize_mobile("09123456789"), "09123456789")
        self.assertEqual(normalize_mobile("+989123456789"), "09123456789")
        self.assertEqual(normalize_mobile("989123456789"), "09123456789")
        self.assertEqual(normalize_mobile("9123456789"), "09123456789")

    def test_rejects_invalid(self):
        for bad in ("123", "08123456789", "0912345678", "", None, "abcdefghijk"):
            with self.assertRaises(ValueError):
                normalize_mobile(bad)


class SmsLoginFlowTests(TestCase):
    def setUp(self):
        # Throttle history lives in the shared locmem cache across tests;
        # reset it so one test's requests never throttle the next one.
        cache.clear()

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="smsagent", password="agentpass123", role=UserRole.AGENT
        )
        self.profile = ConsultantProfile.objects.create(
            user=self.user,
            full_name="Sms Agent",
            mobile="09123456789",
            branch="شعبه مرکزی",
            is_active=True,
        )
        set_login_method(LoginMethod.SMS)

        # The view binds `send_verification_code` into its own namespace
        # (from-import), so patch where it is *used*, not where it is defined.
        patcher_send = mock.patch("apps.accounts.views.send_verification_code")
        patcher_gen = mock.patch("apps.accounts.sms._generate_code", return_value="123456")
        self.mock_send = patcher_send.start()
        self.mock_gen = patcher_gen.start()
        self.addCleanup(patcher_send.stop)
        self.addCleanup(patcher_gen.stop)
        self.addCleanup(lambda: set_login_method(LoginMethod.PASSWORD))

    def _request(self, mobile="09123456789"):
        return self.client.post("/accounts/sms-login/request/", {"mobile": mobile}, format="json")

    def _verify(self, code="123456", mobile="09123456789"):
        return self.client.post(
            "/accounts/sms-login/verify/", {"mobile": mobile, "code": code}, format="json"
        )

    def test_request_code_sends_sms(self):
        res = self._request()
        self.assertEqual(res.status_code, 200)
        self.mock_send.assert_called_once_with("09123456789", "123456")
        self.assertTrue(SmsLoginCode.objects.filter(mobile="09123456789").exists())

    def test_request_code_normalizes_mobile(self):
        res = self._request(mobile="+989123456789")
        self.assertEqual(res.status_code, 200)
        self.mock_send.assert_called_once_with("09123456789", "123456")

    def test_request_code_unknown_mobile_is_generic(self):
        res = self._request(mobile="09999999999")
        self.assertEqual(res.status_code, 200)
        self.mock_send.assert_not_called()

    def test_request_code_invalid_mobile(self):
        res = self._request(mobile="123")
        self.assertEqual(res.status_code, 400)

    def test_request_code_disabled_when_password_active(self):
        set_login_method(LoginMethod.PASSWORD)
        res = self._request()
        self.assertEqual(res.status_code, 400)

    def test_resend_cooldown(self):
        self.assertEqual(self._request().status_code, 200)
        self.assertEqual(self._request().status_code, 429)

    def test_verify_correct_code_logs_in(self):
        self._request()
        res = self._verify()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.id))
        code = SmsLoginCode.objects.get(mobile="09123456789")
        self.assertIsNotNone(code.consumed_at)

    def test_verify_wrong_code(self):
        self._request()
        res = self._verify(code="000000")
        self.assertEqual(res.status_code, 400)
        code = SmsLoginCode.objects.get(mobile="09123456789")
        self.assertEqual(code.attempts, 1)

    def test_verify_too_many_attempts_invalidates_code(self):
        self._request()
        for _ in range(sms.otp_max_attempts()):
            self._verify(code="000000")
        res = self._verify(code="123456")
        self.assertEqual(res.status_code, 400)
        self.assertIn("باطل", res.data["detail"])

    def test_verify_expired_code(self):
        self._request()
        code = SmsLoginCode.objects.get(mobile="09123456789")
        code.expires_at = timezone.now() - timedelta(seconds=1)
        code.save(update_fields=["expires_at"])
        res = self._verify()
        self.assertEqual(res.status_code, 400)

    def test_archived_consultant_cannot_verify(self):
        self.profile.is_active = False
        self.profile.save()
        sms.issue_code("09123456789")
        res = self._verify()
        self.assertEqual(res.status_code, 400)
        self.assertIn(INACTIVE_ACCOUNT_MESSAGE, res.data["detail"])


class SmsProviderFallbackTests(TestCase):
    def setUp(self):
        config = SmsProviderSettings.get_solo()
        config.smsir_api_key = "smsir-key"
        config.smsir_template_id = "12345"
        config.kavenegar_api_key = "kave-key"
        config.kavenegar_sender = "20006535"
        config.kavenegar_message = "code: {code}"
        config.save()

    def test_kavenegar_used_when_smsir_fails(self):
        with mock.patch("apps.accounts.sms._smsir_send", side_effect=SmsSendError("down")), \
                mock.patch("apps.accounts.sms._kavenegar_send") as kave:
            sms.send_verification_code("09123456789", "123456")
            kave.assert_called_once()

    def test_error_when_both_providers_fail(self):
        with mock.patch("apps.accounts.sms._smsir_send", side_effect=SmsSendError("down")), \
                mock.patch("apps.accounts.sms._kavenegar_send", side_effect=SmsSendError("down")):
            with self.assertRaises(SmsSendError):
                sms.send_verification_code("09123456789", "123456")


class LoginMethodEnforcementTests(TestCase):
    def setUp(self):
        cache.clear()
        # The admin login form requires is_staff in addition to the ADMIN
        # role, so the fixture must be staff (create_user alone is not).
        self.user = User.objects.create_user(
            username="switcher",
            password="adminpass123",
            role=UserRole.ADMIN,
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.user, full_name="Switcher", branch="شعبه مرکزی")
        self.addCleanup(lambda: set_login_method(LoginMethod.PASSWORD))

    def test_password_login_blocked_when_sms_active(self):
        set_login_method(LoginMethod.SMS)
        res = Client().post(
            "/accounts/login/", {"username": "switcher", "password": "adminpass123"}
        )
        self.assertEqual(res.status_code, 200)
        errors = extract_login_errors(res.content.decode("utf-8"))
        self.assertIn(SMS_LOGIN_REQUIRED_MESSAGE, errors.get("__all__", []))

    def test_admin_form_still_allows_password_when_sms_active(self):
        set_login_method(LoginMethod.SMS)
        form = ZaminexAdminAuthenticationForm(
            data={"username": "switcher", "password": "adminpass123"}
        )
        self.assertTrue(form.is_valid())

    def test_login_options_endpoint_admin_only(self):
        agent = User.objects.create_user(
            username="agentx", password="agentpass123", role=UserRole.AGENT
        )
        client = APIClient()
        client.force_authenticate(user=agent)
        res = client.patch("/accounts/login-options/", {"method": "sms"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_login_options_roundtrip(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.patch("/accounts/login-options/", {"method": "sms"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(LoginSettings.get_solo().method, LoginMethod.SMS)
        res = client.get("/accounts/login-options/")
        self.assertEqual(res.data["method"], LoginMethod.SMS)
