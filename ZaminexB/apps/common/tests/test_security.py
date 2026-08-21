"""End-to-end checks for the security hardening pass."""

import json
from io import BytesIO

from django.contrib.auth import get_user, get_user_model
from django.conf import settings
from django.test import Client, TestCase
from pathlib import Path
from rest_framework.test import APIClient

from apps.accounts.models import ConsultantProfile, LoginAttempt, UserRole
from apps.common.ai_url import UnsafeAIURL, assert_public_https_url
from apps.followups.models import FollowUp, FollowUpType
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task

User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()


def _user(username, role, **extra):
    return User.objects.create_user(username=username, password="pw-secret-1", role=role, **extra)


def _property(code, consultant, **extra):
    defaults = dict(
        title=f"ملک {code}",
        internal_code=code,
        consultant=consultant,
        property_type="APARTMENT",
        deal_type="SALE",
        area=80,
        address="تهران",
    )
    defaults.update(extra)
    return Property.objects.create(**defaults)


class FollowUpAuthTests(TestCase):
    def setUp(self):
        self.agent = _user("sec-agent", UserRole.AGENT)
        self.other = _user("sec-agent-2", UserRole.AGENT)
        self.admin = _user("sec-admin", UserRole.ADMIN)
        self.mine = _property("SEC-1", self.agent)
        self.theirs = _property("SEC-2", self.other)

    def test_anonymous_cannot_create_or_list_followups(self):
        client = APIClient()
        listed = client.get("/followupa/api/followups/")
        self.assertIn(listed.status_code, (401, 403))
        created = client.post(
            "/followupa/api/followups/",
            {
                "title": "تماس",
                "type": "Call",
                "contact": "علی",
                "date": "2026-08-14T10:00:00Z",
                "consultantId": self.agent.id,
                "propertyId": self.mine.id,
            },
            format="json",
        )
        self.assertIn(created.status_code, (401, 403))
        self.assertFalse(FollowUp.objects.exists())

    def test_consultant_cannot_create_followup_for_another_agent(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        resp = client.post(
            "/followupa/api/followups/",
            {
                "title": "تماس",
                "type": "Call",
                "contact": "علی",
                "date": "2026-08-14T10:00:00Z",
                "consultantId": self.other.id,
                "propertyId": self.mine.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content[:300])
        self.assertEqual(resp.json()["consultantId"], self.agent.id)
        self.assertEqual(FollowUp.objects.get().consultant_id, self.agent.id)

    def test_consultant_cannot_attach_followup_to_foreign_private_property(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        resp = client.post(
            "/followupa/api/followups/",
            {
                "title": "تماس",
                "type": "Call",
                "contact": "علی",
                "date": "2026-08-14T10:00:00Z",
                "consultantId": self.agent.id,
                "propertyId": self.theirs.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(FollowUp.objects.exists())


class PropertyIdorTests(TestCase):
    def setUp(self):
        self.owner = _user("own-agent", UserRole.AGENT)
        self.other = _user("oth-agent", UserRole.AGENT)
        self.admin = _user("own-admin", UserRole.ADMIN)
        self.shared = _property("SHR-1", self.owner, is_shared=True)
        self.private = _property("PRV-1", self.owner, is_shared=False)

    def test_other_consultant_cannot_delete_shared_property(self):
        client = APIClient()
        client.force_authenticate(user=self.other)
        resp = client.delete(f"/properties/api/properties/{self.shared.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Property.objects.filter(pk=self.shared.id).exists())

    def test_owner_can_delete_own_property(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        resp = client.delete(f"/properties/api/properties/{self.private.id}/")
        self.assertIn(resp.status_code, (200, 204))
        self.assertFalse(Property.objects.filter(pk=self.private.id).exists())

    def test_consultant_cannot_flip_is_shared(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        resp = client.patch(
            f"/properties/api/properties/{self.private.id}/",
            {"isShared": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.private.refresh_from_db()
        self.assertFalse(self.private.is_shared)

    def test_other_consultant_cannot_archive_shared_property(self):
        client = APIClient()
        client.force_authenticate(user=self.other)
        resp = client.patch(
            f"/properties/api/properties/{self.shared.id}/",
            {"status": "INACTIVE"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.shared.refresh_from_db()
        self.assertNotEqual(self.shared.status, Property.Status.INACTIVE)


class ListingAndTaskScopeTests(TestCase):
    def setUp(self):
        self.agent = _user("lst-agent", UserRole.AGENT)
        self.other = _user("lst-other", UserRole.AGENT)
        self.foreign = _property("LST-F", self.other)

    def test_consultant_cannot_create_listing_on_foreign_property(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        resp = client.post(
            "/listings/api/listings/",
            {
                "title": "آگهی غیرمجاز",
                "property": self.foreign.id,
                "publish_channel": "WEBSITE",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Listing.objects.exists())

    def test_consultant_cannot_create_task_on_foreign_property(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        resp = client.post(
            "/tasks/api/tasks/",
            {
                "title": "وظیفه غیرمجاز",
                "property": self.foreign.id,
                "status": "PENDING",
                "priority": "MEDIUM",
                "task_type": "VIEWING",
                "due_date": "2026-08-20",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Task.objects.exists())


class SessionInvalidationTests(TestCase):
    def setUp(self):
        self.agent = _user("sess-agent", UserRole.AGENT)
        ConsultantProfile.objects.create(user=self.agent, full_name="مشاور", branch="مرکزی")
        self.admin = _user("sess-admin", UserRole.ADMIN, is_staff=True)

    def test_self_password_change_keeps_current_session_and_drops_others(self):
        first = Client()
        second = Client()
        self.assertTrue(first.login(username="sess-agent", password="pw-secret-1"))
        self.assertTrue(second.login(username="sess-agent", password="pw-secret-1"))

        resp = first.post(
            "/accounts/consultants/change-password/",
            data=json.dumps({
                "current_password": "pw-secret-1",
                "new_password": "brand-new-pass",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])

        self.assertTrue(get_user(first).is_authenticated)
        second_resp = second.get("/accounts/consultants/me/")
        self.assertIn(second_resp.status_code, (401, 403))

    def test_admin_password_change_drops_target_sessions(self):
        victim = Client()
        self.assertTrue(victim.login(username="sess-agent", password="pw-secret-1"))

        admin = APIClient()
        admin.force_authenticate(user=self.admin)
        resp = admin.post(
            f"/common/api/admin-password-change/{self.agent.id}/",
            {"new_password": "reset-pass-99", "confirm_password": "reset-pass-99"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        victim_resp = victim.get("/accounts/consultants/me/")
        self.assertIn(victim_resp.status_code, (401, 403))

    def test_profile_patch_cannot_set_password(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        resp = client.patch(
            "/accounts/consultants/me/",
            {"password": "hijacked-pass"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.check_password("pw-secret-1"))
        self.assertFalse(self.agent.check_password("hijacked-pass"))


class AdminPanelAccessTests(TestCase):
    def setUp(self):
        self.admin = _user("adm-ok", UserRole.ADMIN, is_staff=True)
        self.agent_staff = _user("adm-agent", UserRole.AGENT, is_staff=True)

    def test_staff_agent_cannot_open_admin(self):
        client = Client()
        client.force_login(self.agent_staff)
        resp = client.get("/admin/")
        self.assertNotEqual(resp.status_code, 200)

    def test_admin_staff_can_open_admin(self):
        client = Client()
        client.force_login(self.admin)
        resp = client.get("/admin/")
        self.assertEqual(resp.status_code, 200)

    def test_admin_login_uses_account_lockout(self):
        for _ in range(5):
            self.client.post("/admin/login/", {"username": "adm-ok", "password": "wrong"})
        locked = LoginAttempt.objects.get(username="adm-ok")
        self.assertIsNotNone(locked.locked_until)


class MediaAuthTests(TestCase):
    def setUp(self):
        self.agent = _user("media-agent", UserRole.AGENT)

    def test_anonymous_cannot_read_media(self):
        media_root = Path(settings.MEDIA_ROOT)
        media_root.mkdir(parents=True, exist_ok=True)
        target = media_root / "sec-probe.txt"
        target.write_bytes(b"secret-bytes")

        anon = Client()
        denied = anon.get("/media/sec-probe.txt")
        self.assertEqual(denied.status_code, 403)

        logged = Client()
        logged.force_login(self.agent)
        # Unknown/loose files under MEDIA_ROOT are now denied by default:
        # only known profile/property images with an owner are served.
        allowed = logged.get("/media/sec-probe.txt")
        self.assertEqual(allowed.status_code, 403)


class PublicEndpointTests(TestCase):
    def test_login_stats_remain_public(self):
        resp = self.client.get("/common/api/login-stats/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("totalProperties", resp.json())

    def test_districts_require_authentication(self):
        resp = self.client.get("/common/api/districts/")
        self.assertIn(resp.status_code, (401, 403))


class AIUrlGuardTests(TestCase):
    def test_rejects_http_and_private_hosts(self):
        for raw in (
            "http://api.openai.com/v1",
            "https://127.0.0.1/v1",
            "https://localhost/v1",
            "https://169.254.169.254/latest",
            "https://192.168.1.10/v1",
            "file:///etc/passwd",
        ):
            with self.assertRaises(UnsafeAIURL):
                assert_public_https_url(raw)

    def test_accepts_public_https(self):
        self.assertTrue(assert_public_https_url("https://1.1.1.1/v1").startswith("https://"))


class ProtectedMediaTests(TestCase):
    def setUp(self):
        self.admin = _user("media-admin", UserRole.ADMIN)
        self.owner = _user("media-owner", UserRole.AGENT)
        self.other = _user("media-other", UserRole.AGENT)
        ConsultantProfile.objects.create(
            user=self.owner, full_name="Owner", branch="B"
        )
        self.prop = _property("MEDIA-1", self.owner)
        # Avoid touching disk: use an in-memory file for the DB row.
        from django.core.files.base import ContentFile
        from apps.properties.models import PropertyImage
        self.image = PropertyImage.objects.create(
            property=self.prop,
            image=ContentFile(b"png-bytes", name="properties/images/secret.png"),
        )
        self.rel_path = self.image.image.name

    def test_anonymous_is_denied(self):
        resp = self.client.get(f"/media/{self.rel_path}")
        self.assertEqual(resp.status_code, 403)

    def test_other_consultant_cannot_download(self):
        self.client.force_login(self.other)
        resp = self.client.get(f"/media/{self.rel_path}")
        self.assertEqual(resp.status_code, 403)

    def test_owner_and_admin_can_download(self):
        self.client.force_login(self.owner)
        resp = self.client.get(f"/media/{self.rel_path}")
        self.assertEqual(resp.status_code, 200)
        self.client.force_login(self.admin)
        resp = self.client.get(f"/media/{self.rel_path}")
        self.assertEqual(resp.status_code, 200)

    def test_path_traversal_is_rejected(self):
        self.client.force_login(self.admin)
        resp = self.client.get("/media/properties/images/../../config/settings.py")
        self.assertIn(resp.status_code, (400, 403, 404))

    def test_shared_property_is_accessible(self):
        self.prop.is_shared = True
        self.prop.save(update_fields=["is_shared"])
        self.client.force_login(self.other)
        resp = self.client.get(f"/media/{self.rel_path}")
        self.assertEqual(resp.status_code, 200)
