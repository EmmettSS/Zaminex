import shutil
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.properties.models import Property

User = get_user_model()


class PropertyConsultantRoleApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="role-admin",
            password="pw",
            role="ADMIN",
            first_name="مدیر",
            last_name="سیستم",
        )
        self.agent = User.objects.create_user(
            username="role-agent",
            password="pw",
            role="AGENT",
            first_name="سارا",
            last_name="احمدی",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.prop = Property.objects.create(
            title="ملک نقش مشاور",
            internal_code="ZF_9001",
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            area=90,
            address="تهران",
        )

    def test_detail_reports_the_assigned_consultant_role(self):
        resp = self.client.get(f"/properties/api/properties/{self.prop.id}/")
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        data = resp.json()
        self.assertEqual(data["consultantId"], self.agent.id)
        self.assertEqual(data["consultantRole"], "AGENT")
        self.assertNotEqual(data["consultantRole"], "ADMIN")
        self.assertNotIn("مشاور ارشد", str(data))

    def test_list_reports_the_assigned_consultant_role(self):
        resp = self.client.get("/properties/api/properties/")
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        payload = resp.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        row = next(item for item in rows if item["internalCode"] == "ZF_9001")
        self.assertEqual(row["consultantRole"], self.agent.role)
        self.assertEqual(row["consultantRole"], "AGENT")


class PropertyLocationApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="loc-admin", password="pw", role="ADMIN")
        self.agent = User.objects.create_user(username="loc-agent", password="pw", role="AGENT")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_create_and_update_persist_coordinates(self):
        create = self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک با موقعیت",
                "internalCode": "LOC-1",
                "type": "APARTMENT",
                "transactionType": "SALE",
                "area": 80,
                "fullAddress": "ساری",
                "consultant": self.agent.id,
                "ownerFirstName": "علی",
                "ownerLastName": "رضایی",
                "ownerPhone": "09121234567",
                "latitude": "36.563421",
                "longitude": "53.060112",
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.content[:400])
        created = create.json()
        self.assertAlmostEqual(float(created["latitude"]), 36.563421, places=6)
        self.assertAlmostEqual(float(created["longitude"]), 53.060112, places=6)

        detail = self.client.get(f"/properties/api/properties/{created['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertAlmostEqual(float(detail.json()["latitude"]), 36.563421, places=6)
        self.assertAlmostEqual(float(detail.json()["longitude"]), 53.060112, places=6)

        patched = self.client.patch(
            f"/properties/api/properties/{created['id']}/",
            {"latitude": "35.689198", "longitude": "51.389973"},
            format="json",
        )
        self.assertEqual(patched.status_code, 200, patched.content[:400])
        self.assertAlmostEqual(float(patched.json()["latitude"]), 35.689198, places=6)
        self.assertAlmostEqual(float(patched.json()["longitude"]), 51.389973, places=6)

        agent_client = APIClient()
        agent_client.force_authenticate(user=self.agent)
        agent_view = agent_client.get(f"/properties/api/properties/{created['id']}/")
        self.assertEqual(agent_view.status_code, 200)
        self.assertAlmostEqual(float(agent_view.json()["latitude"]), 35.689198, places=6)
        self.assertAlmostEqual(float(agent_view.json()["longitude"]), 51.389973, places=6)

    def test_consultant_can_create_and_change_coordinates(self):
        agent_client = APIClient()
        agent_client.force_authenticate(user=self.agent)
        create = agent_client.post(
            "/properties/api/properties/",
            {
                "title": "ملک مشاور با موقعیت",
                "internalCode": "LOC-AGENT-1",
                "type": "APARTMENT",
                "transactionType": "SALE",
                "area": 70,
                "fullAddress": "تهران",
                "ownerFirstName": "مریم",
                "ownerLastName": "حسینی",
                "ownerPhone": "09112223344",
                "latitude": "35.700123",
                "longitude": "51.400456",
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.content[:400])
        created = create.json()
        self.assertAlmostEqual(float(created["latitude"]), 35.700123, places=6)
        self.assertAlmostEqual(float(created["longitude"]), 51.400456, places=6)

        patched = agent_client.patch(
            f"/properties/api/properties/{created['id']}/",
            {"latitude": "36.297000", "longitude": "59.606000"},
            format="json",
        )
        self.assertEqual(patched.status_code, 200, patched.content[:400])
        self.assertAlmostEqual(float(patched.json()["latitude"]), 36.297000, places=6)
        self.assertAlmostEqual(float(patched.json()["longitude"]), 59.606000, places=6)


class PropertyImageAccessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="img-admin", password="pw", role="ADMIN"
        )
        self.owner = User.objects.create_user(
            username="img-owner", password="pw", role="AGENT"
        )
        self.stranger = User.objects.create_user(
            username="img-stranger", password="pw", role="AGENT"
        )
        self.prop = Property.objects.create(
            title="ملک تصویر",
            internal_code="IMG-1",
            consultant=self.owner,
            property_type="APARTMENT",
            deal_type="SALE",
            area=80,
            address="تهران",
        )

    def _upload(self, user):
        from django.core.files.uploadedfile import SimpleUploadedFile
        client = APIClient()
        client.force_authenticate(user=user)
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000a0000000a0802000000025058ea"
            "0000001249444154789c63fccf800f30e1951db1d200412c0113b10a73130000000049454e44ae426082"
        )
        f = SimpleUploadedFile("t.png", png, content_type="image/png")
        return client.post(
            f"/properties/api/properties/{self.prop.id}/images/",
            {"images": f},
            format="multipart",
            SERVER_NAME="testserver",
        )

    def test_owner_and_admin_can_upload(self):
        self.assertEqual(self._upload(self.owner).status_code, 201)
        self.assertEqual(self._upload(self.admin).status_code, 201)

    def test_stranger_cannot_upload(self):
        resp = self._upload(self.stranger)
        self.assertIn(resp.status_code, (403, 404))

    def test_stranger_cannot_delete(self):
        from apps.properties.models import PropertyImage
        created = self._upload(self.owner)
        image_id = created.json()[0]["id"]
        client = APIClient()
        client.force_authenticate(user=self.stranger)
        resp = client.delete(
            f"/properties/api/properties/{self.prop.id}/images/{image_id}/"
        )
        self.assertIn(resp.status_code, (403, 404))
        self.assertTrue(PropertyImage.objects.filter(pk=image_id).exists())

    def test_owner_can_delete(self):
        created = self._upload(self.owner)
        image_id = created.json()[0]["id"]
        client = APIClient()
        client.force_authenticate(user=self.owner)
        resp = client.delete(
            f"/properties/api/properties/{self.prop.id}/images/{image_id}/"
        )
        self.assertEqual(resp.status_code, 204)

    def test_stranger_cannot_reorder(self):
        created = self._upload(self.owner)
        image_id = created.json()[0]["id"]
        client = APIClient()
        client.force_authenticate(user=self.stranger)
        resp = client.patch(
            f"/properties/api/properties/{self.prop.id}/images-reorder/",
            [{"id": image_id, "sort_order": 5}],
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_upload_rejects_non_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        client = APIClient()
        client.force_authenticate(user=self.owner)
        fake = SimpleUploadedFile("x.png", b"not a real png", content_type="image/png")
        resp = client.post(
            f"/properties/api/properties/{self.prop.id}/images/",
            {"images": fake},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400, resp.content[:400])


class PropertyOwnerFieldsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="owner-admin", password="pw", role="ADMIN"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_create_requires_owner_info(self):
        resp = self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک بدون مالک",
                "type": "APARTMENT",
                "transactionType": "SALE",
                "area": 80,
                "fullAddress": "تهران",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content[:400])
        body = resp.json()
        self.assertIn("owner_first_name", body)
        self.assertIn("owner_last_name", body)
        self.assertIn("owner_phone", body)

    def test_create_and_read_owner_info(self):
        resp = self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک با مالک",
                "type": "APARTMENT",
                "transactionType": "SALE",
                "area": 80,
                "fullAddress": "تهران",
                "ownerFirstName": "علی",
                "ownerLastName": "رضایی",
                "ownerPhone": "09121234567",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content[:400])
        created = resp.json()
        self.assertEqual(created["ownerFirstName"], "علی")
        self.assertEqual(created["ownerLastName"], "رضایی")
        self.assertEqual(created["ownerPhone"], "09121234567")

        detail = self.client.get(f"/properties/api/properties/{created['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["ownerFirstName"], "علی")

    def test_update_can_fill_owner_info(self):
        prop = Property.objects.create(
            title="ملک بدون مالک",
            internal_code="ZF_9301",
            consultant=self.admin,
            property_type="APARTMENT",
            deal_type="SALE",
            area=80,
            address="تهران",
        )
        resp = self.client.patch(
            f"/properties/api/properties/{prop.id}/",
            {
                "ownerFirstName": "سارا",
                "ownerLastName": "موسوی",
                "ownerPhone": "09129998877",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        data = resp.json()
        self.assertEqual(data["ownerFirstName"], "سارا")
        self.assertEqual(data["ownerPhone"], "09129998877")

    def test_owner_phone_must_be_11_digits_starting_09(self):
        for bad in ("0912123456", "19121234567", "091212345678", "09121234a67", ""):
            resp = self.client.post(
                "/properties/api/properties/",
                {
                    "title": "ملک موبایل نامعتبر",
                    "type": "APARTMENT",
                    "transactionType": "SALE",
                    "area": 80,
                    "fullAddress": "تهران",
                    "ownerFirstName": "علی",
                    "ownerLastName": "رضایی",
                    "ownerPhone": bad,
                },
                format="json",
            )
            
            self.assertEqual(resp.status_code, 400, f"{bad!r}: {resp.content[:300]}")
            self.assertIn("owner_phone", resp.json())
        self.assertEqual(Property.objects.filter(title="ملک موبایل نامعتبر").count(), 0)

    def test_partial_update_without_phone_is_not_blocked(self):
        prop = Property.objects.create(
            title="ملک بدون موبایل",
            internal_code="ZF_9302",
            consultant=self.admin,
            property_type="APARTMENT",
            deal_type="SALE",
            area=80,
            address="تهران",
        )
        resp = self.client.patch(
            f"/properties/api/properties/{prop.id}/",
            {"title": "فقط تغییر عنوان"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])


class PropertyScopeAllAccessTests(TestCase):
    def setUp(self):
        self.agent1 = User.objects.create_user(
            username="scope-agent1", password="pw", role="AGENT"
        )
        self.agent2 = User.objects.create_user(
            username="scope-agent2", password="pw", role="AGENT"
        )
        self.mine = Property.objects.create(
            title="ملک من",
            internal_code="ZF_9101",
            consultant=self.agent1,
            property_type="APARTMENT",
            deal_type="SALE",
            area=80,
            address="تهران",
            owner_first_name="الف",
            owner_last_name="ب",
            owner_phone="0",
        )
        self.other = Property.objects.create(
            title="ملک دیگری",
            internal_code="ZF_9102",
            consultant=self.agent2,
            property_type="APARTMENT",
            deal_type="SALE",
            area=90,
            address="شیراز",
            owner_first_name="ج",
            owner_last_name="د",
            owner_phone="1",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.agent1)

    def test_list_without_scope_is_restricted_to_own(self):
        resp = self.client.get("/properties/api/properties/")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        codes = {r["internalCode"] for r in rows}
        self.assertIn("ZF_9101", codes)
        self.assertNotIn("ZF_9102", codes)

    def test_list_with_scope_all_shows_everything(self):
        resp = self.client.get("/properties/api/properties/?scope=all")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        codes = {r["internalCode"] for r in rows}
        self.assertIn("ZF_9101", codes)
        self.assertIn("ZF_9102", codes)

    def test_consultant_can_read_other_detail_with_scope_all(self):
        resp = self.client.get(
            f"/properties/api/properties/{self.other.id}/?scope=all"
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])

    def test_consultant_cannot_read_other_detail_without_scope(self):
        resp = self.client.get(f"/properties/api/properties/{self.other.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_consultant_cannot_update_other_non_shared(self):
        resp = self.client.patch(
            f"/properties/api/properties/{self.other.id}/?scope=all",
            {"title": "تغییر غیرمجاز"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_consultant_cannot_delete_other_non_shared(self):
        resp = self.client.delete(f"/properties/api/properties/{self.other.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_consultant_can_update_own_property(self):
        resp = self.client.patch(
            f"/properties/api/properties/{self.mine.id}/",
            {"title": "ملک من ویرایش شد"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])


class PropertyAppraisalReportApiTests(TestCase):
    PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF\n"

    def setUp(self):
        import tempfile
        from django.conf import settings

        self.admin = User.objects.create_user(
            username="appr-admin", password="pw", role="ADMIN"
        )
        self.owner = User.objects.create_user(
            username="appr-owner", password="pw", role="AGENT"
        )
        self.stranger = User.objects.create_user(
            username="appr-stranger", password="pw", role="AGENT"
        )
        self.prop = Property.objects.create(
            title="ملک گزارش کارشناسی",
            internal_code="APPR-1",
            consultant=self.owner,
            property_type="APARTMENT",
            deal_type="SALE",
            area=80,
            address="تهران",
        )
        tmp = tempfile.mkdtemp(prefix="zaminex-appr-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=tmp)
        override.enable()
        self.addCleanup(override.disable)

    def _pdf(self, name="گزارش کارشناسی.pdf", content=None):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(
            name, content if content is not None else self.PDF_BYTES,
            content_type="application/pdf",
        )

    def _upload(self, user, f=None, prop=None):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.post(
            f"/properties/api/properties/{(prop or self.prop).id}/appraisal-report/",
            {"file": f or self._pdf()},
            format="multipart",
        )

    def _current_report(self):
        from apps.properties.models import PropertyAppraisalReport

        return PropertyAppraisalReport.objects.filter(property=self.prop).first()

    def test_owner_and_admin_can_upload(self):
        first = self._upload(self.owner)
        self.assertEqual(first.status_code, 201, first.content[:400])
        body = first.json()
        self.assertEqual(body["fileName"], "گزارش کارشناسی.pdf")
        self.assertEqual(body["fileSize"], len(self.PDF_BYTES))
        self.assertIn("appraisal-report/download", body["url"])
        self.assertEqual(body["uploadedBy"], "appr-owner")

    def test_upload_replaces_previous_file(self):
        from apps.properties.models import PropertyAppraisalReport

        first = self._upload(self.owner, self._pdf(name="first.pdf"))
        first_path = PropertyAppraisalReport.objects.get(
            property=self.prop
        ).file.name

        second = self._upload(self.owner, self._pdf(name="second.pdf"))
        self.assertEqual(second.status_code, 201, second.content[:400])
        self.assertEqual(second.json()["fileName"], "second.pdf")
        self.assertEqual(
            PropertyAppraisalReport.objects.filter(property=self.prop).count(), 1
        )
        report = self._current_report()
        self.assertNotEqual(report.file.name, first_path)
        self.assertTrue(report.file.storage.exists(report.file.name))
        self.assertFalse(report.file.storage.exists(first_path))

    def test_upload_rejects_non_pdf_extension(self):
        resp = self._upload(self.owner, self._pdf(name="report.png"))
        self.assertEqual(resp.status_code, 400, resp.content[:400])
        self.assertIsNone(self._current_report())

    def test_upload_rejects_fake_pdf_content(self):
        resp = self._upload(self.owner, self._pdf(name="fake.pdf", content=b"<html>x</html>"))
        self.assertEqual(resp.status_code, 400, resp.content[:400])
        self.assertIsNone(self._current_report())

    def test_upload_rejects_oversized_file(self):
        oversized = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024)
        resp = self._upload(self.owner, self._pdf(name="big.pdf", content=oversized))
        self.assertEqual(resp.status_code, 400, resp.content[:400])
        self.assertIsNone(self._current_report())

    def test_upload_requires_a_file(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        resp = client.post(
            f"/properties/api/properties/{self.prop.id}/appraisal-report/",
            {},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)

    def test_stranger_cannot_upload(self):
        resp = self._upload(self.stranger)
        self.assertIn(resp.status_code, (403, 404))
        self.assertIsNone(self._current_report())

    def test_owner_can_delete(self):
        self._upload(self.owner)
        report = self._current_report()
        stored = report.file.name

        client = APIClient()
        client.force_authenticate(user=self.owner)
        resp = client.delete(
            f"/properties/api/properties/{self.prop.id}/appraisal-report/"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertIsNone(self._current_report())
        self.assertFalse(report.file.storage.exists(stored))

    def test_delete_without_report_is_404(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        resp = client.delete(
            f"/properties/api/properties/{self.prop.id}/appraisal-report/"
        )
        self.assertEqual(resp.status_code, 404)

    def test_stranger_cannot_delete(self):
        self._upload(self.owner)
        client = APIClient()
        client.force_authenticate(user=self.stranger)
        resp = client.delete(
            f"/properties/api/properties/{self.prop.id}/appraisal-report/"
        )
        self.assertIn(resp.status_code, (403, 404))
        self.assertIsNotNone(self._current_report())

    def _download(self, user, prop=None, **params):
        client = APIClient()
        client.force_authenticate(user=user)
        from urllib.parse import urlencode

        query = f"?{urlencode(params)}" if params else ""
        return client.get(
            f"/properties/api/properties/{(prop or self.prop).id}/appraisal-report/download/{query}"
        )

    def test_owner_can_download_with_original_filename(self):
        self._upload(self.owner, self._pdf(name="گزارش نهایی.pdf"))
        resp = self._download(self.owner)
        self.assertEqual(resp.status_code, 200, getattr(resp, "content", b"")[:200])
        self.assertEqual(resp["Content-Type"], "application/pdf")
        disposition = resp["Content-Disposition"]
        self.assertIn("attachment", disposition)
        self.assertIn("filename*", disposition)
        self.assertIn("%DA%AF%D8%B2%D8%A7%D8%B1%D8%B4", disposition.upper())

    def test_download_supports_inline_preview(self):
        self._upload(self.owner)
        resp = self._download(self.owner, inline="1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("inline", resp["Content-Disposition"])

    def test_download_missing_report_is_404(self):
        resp = self._download(self.owner)
        self.assertEqual(resp.status_code, 404)

    def test_stranger_cannot_download_non_shared(self):
        self._upload(self.owner)
        resp = self._download(self.stranger, scope="all")
        self.assertEqual(resp.status_code, 403)

    def test_shared_property_download_by_any_consultant(self):
        shared = Property.objects.create(
            title="ملک اشتراکی",
            internal_code="APPR-2",
            consultant=self.owner,
            property_type="VILLA",
            deal_type="SALE",
            area=120,
            address="تهران",
            is_shared=True,
        )
        self._upload(self.owner, prop=shared)
        resp = self._download(self.stranger, prop=shared, scope="all")
        self.assertEqual(resp.status_code, 200)

    def test_property_detail_serializer_exposes_report(self):
        self._upload(self.owner)
        client = APIClient()
        client.force_authenticate(user=self.owner)
        resp = client.get(f"/properties/api/properties/{self.prop.id}/")
        self.assertEqual(resp.status_code, 200)
        report = resp.json().get("appraisalReport")
        self.assertIsNotNone(report)
        self.assertEqual(report["fileName"], "گزارش کارشناسی.pdf")

    def test_media_path_is_protected_like_images(self):
        from django.test import Client

        self._upload(self.owner)
        rel = self._current_report().file.name

        anon = Client().get(f"/media/{rel}")
        self.assertEqual(anon.status_code, 403)

        denied = Client()
        denied.force_login(self.stranger)
        self.assertEqual(denied.get(f"/media/{rel}").status_code, 403)

        allowed = Client()
        allowed.force_login(self.owner)
        self.assertEqual(allowed.get(f"/media/{rel}").status_code, 200)


class NextInternalCodePreviewTests(TestCase):
    URL = "/properties/api/properties/next-internal-code/"

    def setUp(self):
        self.admin = User.objects.create_user(
            username="code-admin", password="pw", role="ADMIN"
        )
        self.agent = User.objects.create_user(
            username="code-agent", password="pw", role="AGENT"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _preview(self, client=None):
        resp = (client or self.client).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        return resp.json()["internalCode"]

    def test_first_code_is_start_of_sequence(self):
        self.assertEqual(self._preview(), "ZF_1111")

    def test_preview_matches_the_code_stored_on_save(self):
        previewed = self._preview()
        created = self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک پیش‌نمایش کد",
                "internalCode": "FORGED-1",
                "type": "APARTMENT",
                "transactionType": "SALE",
                "area": 80,
                "fullAddress": "ساری",
                "ownerFirstName": "علی",
                "ownerLastName": "رضایی",
                "ownerPhone": "09121234567",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.content[:400])
        self.assertEqual(created.json()["internalCode"], previewed)

    def test_preview_advances_after_a_creation(self):
        self._preview()
        Property.objects.create(
            title="ملک دوم",
            internal_code="ZF_1111",
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            area=80,
            address="ساری",
        )
        self.assertEqual(self._preview(), "ZF_1112")

    def test_preview_skips_codes_containing_zero(self):
        for code in ("ZF_1118", "ZF_1119"):
            Property.objects.create(
                title=f"ملک {code}",
                internal_code=code,
                consultant=self.agent,
                property_type="APARTMENT",
                deal_type="SALE",
                area=80,
                address="ساری",
            )
        self.assertEqual(self._preview(), "ZF_1121")

    def test_agent_can_preview_too(self):
        agent_client = APIClient()
        agent_client.force_authenticate(user=self.agent)
        self.assertEqual(self._preview(agent_client), "ZF_1111")

    def test_anonymous_cannot_preview(self):
        anon = APIClient()
        resp = anon.get(self.URL)
        self.assertEqual(resp.status_code, 403)


class DuplicateLocationApiTests(TestCase):
    BASE = {
        "type": "APARTMENT",
        "transactionType": "SALE",
        "area": 80,
        "fullAddress": "ساری، بلوار کشاورز",
        "ownerFirstName": "علی",
        "ownerLastName": "رضایی",
        "ownerPhone": "09121234567",
    }

    def setUp(self):
        self.admin = User.objects.create_user(
            username="duploc-admin", password="pw", role="ADMIN"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _create(self, **extra):
        payload = {"title": "ملک موقعیت", **self.BASE, **extra}
        return self.client.post("/properties/api/properties/", payload, format="json")

    def test_duplicate_location_is_rejected_on_create(self):
        first = self._create(title="ملک اول", latitude="36.563421", longitude="53.060112")
        self.assertEqual(first.status_code, 201, first.content[:400])

        second = self._create(title="ملک دوم", latitude="36.563421", longitude="53.060112")
        self.assertEqual(second.status_code, 400, second.content[:400])
        body = second.json()
        message = " ".join(
            item for v in body.values() if isinstance(v, list) for item in v
        )
        self.assertIn("یکی باشد", message)
        self.assertIn("ملک اول", message)
        self.assertEqual(Property.objects.count(), 1)

    def test_different_locations_are_allowed(self):
        first = self._create(title="ملک اول", latitude="36.563421", longitude="53.060112")
        second = self._create(title="ملک دوم", latitude="36.563422", longitude="53.060112")
        self.assertEqual(first.status_code, 201, first.content[:400])
        self.assertEqual(second.status_code, 201, second.content[:400])
        self.assertEqual(Property.objects.count(), 2)

    def test_update_to_another_property_location_is_rejected(self):
        first = self._create(title="ملک اول", latitude="36.563421", longitude="53.060112")
        second = self._create(title="ملک دوم", latitude="35.689198", longitude="51.389973")
        second_id = second.json()["id"]

        moved = self.client.patch(
            f"/properties/api/properties/{second_id}/",
            {"latitude": "36.563421", "longitude": "53.060112"},
            format="json",
        )
        self.assertEqual(moved.status_code, 400, moved.content[:400])
        self.assertEqual(
            Property.objects.get(pk=second_id).latitude, Decimal("35.689198")
        )

    def test_update_keeping_its_own_location_is_allowed(self):
        created = self._create(title="ملک ثابت", latitude="36.563421", longitude="53.060112")
        prop_id = created.json()["id"]

        retitled = self.client.patch(
            f"/properties/api/properties/{prop_id}/",
            {
                "title": "ملک ثابت (ویرایش‌شده)",
                "latitude": "36.563421",
                "longitude": "53.060112",
            },
            format="json",
        )
        self.assertEqual(retitled.status_code, 200, retitled.content[:400])

    def test_update_without_coordinates_is_not_blocked(self):
        created = self._create(title="ملک بدون موقعیت")
        prop_id = created.json()["id"]

        retitled = self.client.patch(
            f"/properties/api/properties/{prop_id}/",
            {"title": "بدون مختصات"},
            format="json",
        )
        self.assertEqual(retitled.status_code, 200, retitled.content[:400])
