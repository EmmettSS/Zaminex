import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from apps.accounts.models import ConsultantProfile

User = get_user_model()

PASSWORD = "pw-secret-1"


class ErrorCodeEnvelopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="code-admin", password=PASSWORD, role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="code-agent", password=PASSWORD, role="AGENT"
        )
        ConsultantProfile.objects.create(
            user=cls.agent, full_name="مشاور", branch="مرکزی"
        )

    def test_anonymous_write_reports_not_authenticated(self):
        resp = self.client.post(
            "/basics/api/provinces/",
            data='{"displayName": "الف"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "not_authenticated")

    def test_expired_session_reports_not_authenticated(self):
        self.client.force_login(self.admin)
        self.client.logout()

        resp = self.client.post(
            "/basics/api/provinces/",
            data='{"displayName": "ب"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "not_authenticated")

    def test_permission_denial_reports_permission_denied(self):
        self.client.force_login(self.agent)
        resp = self.client.post(
            "/basics/api/provinces/",
            data='{"displayName": "ج"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "permission_denied")

    def test_csrf_failure_reports_its_own_code(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get("/accounts/login/")

        resp = client.post(
            "/basics/api/provinces/",
            data='{"displayName": "د"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN="not-a-valid-token",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "csrf_failed")

    def test_missing_record_reports_not_found(self):
        self.client.force_login(self.admin)
        resp = self.client.get("/basics/api/provinces/999999/")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "not_found")

    def test_detail_message_is_still_persian(self):
        self.client.force_login(self.agent)
        resp = self.client.post(
            "/basics/api/provinces/",
            data='{"displayName": "ه"}',
            content_type="application/json",
        )
        self.assertEqual(
            resp.json()["detail"], "فقط مدیر می‌تواند اطلاعات پایه را ویرایش کند."
        )


class FieldErrorPayloadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="field-admin", password=PASSWORD, role="ADMIN"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_validation_errors_get_no_code_key(self):
        resp = self.client.post(
            "/basics/api/cities/",
            data='{"displayName": "ساری"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertNotIn("code", payload)
        self.assertEqual(payload["province"], ["انتخاب استان الزامی است."])

    def test_field_errors_keep_their_persian_messages(self):
        resp = self.client.post(
            "/basics/api/districts/",
            data='{"displayName": "آزادی"}',
            content_type="application/json",
        )
        self.assertEqual(resp.json()["city"], ["انتخاب شهر الزامی است."])


class UploadCsrfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="upload-admin", password=PASSWORD, role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="upload-agent", password=PASSWORD, role="AGENT"
        )
        ConsultantProfile.objects.create(
            user=cls.agent, full_name="مشاور آپلود", branch="مرکزی"
        )

    def _png(self):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "blue").save(buf, format="PNG")
        buf.seek(0)
        buf.name = "test.png"
        return buf

    def test_upload_without_csrf_token_is_rejected(self):
        from apps.properties.models import Property

        prop = Property.objects.create(
            title="ملک آپلود",
            internal_code="UPL-1",
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            area=90,
            address="تهران",
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)

        resp = client.post(
            f"/properties/api/properties/{prop.id}/images/",
            {"images": self._png()},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "csrf_failed")

    def test_upload_with_csrf_token_succeeds(self):
        from apps.properties.models import Property

        prop = Property.objects.create(
            title="ملک آپلود ۲",
            internal_code="UPL-2",
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            area=90,
            address="تهران",
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get("/accounts/login/")

        resp = client.post(
            f"/properties/api/properties/{prop.id}/images/",
            {"images": self._png()},
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
