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
            internal_code="ROLE-1",
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
        row = next(item for item in rows if item["internalCode"] == "ROLE-1")
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
