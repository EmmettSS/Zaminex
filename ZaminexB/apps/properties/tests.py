from django.contrib.auth import get_user_model
from django.test import TestCase
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
        # A real 10x10 PNG so the Pillow content check passes.
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000a0000000a0802000000025058ea"
            "0000001249444154789c63fccf800f30e1951db1d200412c0113b10a73130000000049454e44ae426082"
        )
        f = SimpleUploadedFile("t.png", png, content_type="image/png")
        # DRF APIClient uses the testserver host by default; ALLOWED_HOSTS is
        # locked down in test settings, so set it explicitly.
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
        # 403 if somehow visible, but the queryset hides it -> 404.
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
        # Send a text file disguised as an image extension.
        fake = SimpleUploadedFile("x.png", b"not a real png", content_type="image/png")
        resp = client.post(
            f"/properties/api/properties/{self.prop.id}/images/",
            {"images": fake},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400, resp.content[:400])


class PropertyOwnerFieldsApiTests(TestCase):
    """Owner name/surname/mobile are captured on the Property model."""

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


class PropertyScopeAllAccessTests(TestCase):
    """The consultant "همه املاک" tab reads every property but cannot mutate
    another consultant's non-shared records."""

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
        # scope=all only widens reads; mutation stays owner/shared only -> 404.
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
class PropertyInternalCodeSequentialTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="seq-admin", password="pw", role="ADMIN")
        self.agent = User.objects.create_user(username="seq-agent", password="pw", role="AGENT")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_auto_generates_sequential_zf_codes_without_zeros(self):
        p1 = Property.objects.create(
            title="ملک اول",
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            area=100,
            address="تهران",
        )
        self.assertTrue(p1.internal_code.startswith("ZF_"))
        self.assertNotIn("0", p1.internal_code[3:])

        p2 = Property.objects.create(
            title="ملک دوم",
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            area=110,
            address="تهران",
        )
        self.assertTrue(p2.internal_code.startswith("ZF_"))
        self.assertNotIn("0", p2.internal_code[3:])
        self.assertNotEqual(p1.internal_code, p2.internal_code)

    def test_api_ignores_passed_internal_code_and_generates_zf(self):
        resp = self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک تست ای‌پی‌آی",
                "internalCode": "MANUAL-OVERRIDE",
                "type": "APARTMENT",
                "transactionType": "SALE",
                "area": 100,
                "fullAddress": "تهران",
                "consultant": self.agent.id,
                "ownerFirstName": "صمد",
                "ownerLastName": "تست",
                "ownerPhone": "09120000001",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        created_data = resp.json()
        self.assertTrue(created_data["internalCode"].startswith("ZF_"))
        self.assertNotEqual(created_data["internalCode"], "MANUAL-OVERRIDE")
        self.assertNotIn("0", created_data["internalCode"][3:])

