from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.properties.models import Property, PropertyImage

PNG_1x1 = (
    b"89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    b"0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
)


def _png_upload(name: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, PNG_1x1, content_type="image/png")


def _make_property(consultant, **kwargs):
    defaults = dict(
        property_type="APARTMENT",
        deal_type="SALE",
        area=100,
        address="تهران",
    )
    defaults.update(kwargs)
    return Property.objects.create(
        consultant=consultant, **defaults
    )


class PropertyListSerializerShapeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="list-admin", password="pw", role="ADMIN"
        )
        self.agent = User.objects.create_user(
            username="list-agent", password="pw", role="AGENT"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.prop_with_image = _make_property(
            self.agent,
            title="آپارتمان با تصویر",
            internal_code="ZF_1001",
            description="توضیحات طولانی برای بررسی حذف شدن از پاسخ لیست",
            latitude=35.7,
            longitude=51.4,
            owner_first_name="مالک",
            owner_last_name="تست",
            owner_phone="09121234567",
        )
        self.prop_no_image = _make_property(
            self.agent,
            title="ویلای بدون تصویر",
            internal_code="ZF_1002",
            property_type="VILLA",
        )
        self.other_prop = _make_property(
            self.agent,
            title="دفتر مرکزی",
            internal_code="ZF_1003",
        )
        self.image = PropertyImage.objects.create(
            property=self.prop_with_image, image=_png_upload("list-test.png")
        )

    def test_list_response_uses_the_slim_serializer(self):
        res = self.client.get("/properties/api/properties/", {"page_size": 10})
        self.assertEqual(res.status_code, 200)
        row = next(
            r for r in res.json()["results"] if r["id"] == self.prop_with_image.id
        )

        for field in (
            "description",
            "images",
            "appraisalReport",
            "attributes",
            "attributeDetails",
            "pricePerSqm",
            "daysOnMarket",
            "spatialDensityRatio",
            "priceDeviationIndex",
            "geoPrecisionFlag",
            "engagementHeatScore",
            "views",
        ):
            self.assertNotIn(field, row)

        for field in (
            "id",
            "internalCode",
            "title",
            "type",
            "propertyStatus",
            "price",
            "area",
            "beds",
            "district",
            "consultant",
            "consultantName",
            "consultantId",
            "locationPath",
            "latitude",
            "longitude",
            "isShared",
            "ownerFirstName",
            "ownerLastName",
            "ownerPhone",
            "imageUrl",
            "imagesCount",
        ):
            self.assertIn(field, row)

    def test_images_count_is_a_plain_gallery_count(self):
        res = self.client.get("/properties/api/properties/", {"page_size": 10})
        rows = {r["id"]: r for r in res.json()["results"]}
        self.assertEqual(rows[self.prop_with_image.id]["imagesCount"], 1)
        self.assertEqual(rows[self.prop_no_image.id]["imagesCount"], 0)

    def test_image_url_is_the_first_gallery_image(self):
        res = self.client.get("/properties/api/properties/", {"page_size": 10})
        rows = {r["id"]: r for r in res.json()["results"]}
        self.assertTrue(
            rows[self.prop_with_image.id]["imageUrl"].endswith(self.image.image.url)
        )
        self.assertIsNone(rows[self.prop_no_image.id]["imageUrl"])

    def test_detail_response_keeps_the_full_serializer(self):
        res = self.client.get(f"/properties/api/properties/{self.prop_with_image.id}/")
        self.assertEqual(res.status_code, 200)
        row = res.json()
        for field in (
            "description",
            "images",
            "appraisalReport",
            "attributes",
            "attributeDetails",
            "pricePerSqm",
            "imagesCount",
            "daysOnMarket",
            "spatialDensityRatio",
            "priceDeviationIndex",
            "geoPrecisionFlag",
            "engagementHeatScore",
            "views",
        ):
            self.assertIn(field, row)
        self.assertEqual(len(row["images"]), 1)

    def test_create_and_update_responses_use_the_full_serializer(self):
        res = self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک جدید تست",
                "internal_code": "ZF_1009",
                "area": 90,
                "address": "تهران",
                "ownerFirstName": "مالک",
                "ownerLastName": "جدید",
                "ownerPhone": "09121112222",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertIn("description", res.json())
        self.assertIn("images", res.json())

        prop = Property.objects.get(title="ملک جدید تست")
        res = self.client.patch(
            f"/properties/api/properties/{prop.id}/",
            {"area": 95},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("description", res.json())

    def test_list_is_paginated_with_total_count(self):
        res = self.client.get("/properties/api/properties/", {"page_size": 2})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["count"], 3)

        res = self.client.get("/properties/api/properties/", {"page": 2, "page_size": 2})
        self.assertEqual(len(res.json()["results"]), 1)

    def test_search_works_with_the_slim_serializer(self):
        res = self.client.get(
            "/properties/api/properties/", {"q": "آپارتمان", "page_size": 10}
        )
        self.assertEqual(res.status_code, 200)
        rows = res.json()["results"]
        self.assertIn(self.prop_with_image.id, [r["id"] for r in rows])
        self.assertNotIn("description", rows[0])
        self.assertIn("imageUrl", rows[0])


class PropertyListQueryCountTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="qc-admin", password="pw", role="ADMIN"
        )
        self.agent = User.objects.create_user(
            username="qc-agent", password="pw", role="AGENT"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _list_query_count(self, page_size):
        with CaptureQueriesContext(connection) as ctx:
            res = self.client.get(
                "/properties/api/properties/", {"page_size": page_size}
            )
        self.assertEqual(res.status_code, 200)
        return len(ctx.captured_queries)

    def test_query_count_is_constant_regardless_of_rows(self):
        for i in range(5):
            _make_property(
                self.agent,
                title=f"ملک تست {i}",
                internal_code=f"ZF_20{i:02d}",
                description="توضیحات تست " * 5,
            )
        small = self._list_query_count(10)

        from apps.followups.models import FollowUp
        from apps.tasks.models import Task

        for i in range(5, 45):
            prop = _make_property(
                self.agent,
                title=f"ملک تست {i}",
                internal_code=f"ZF_20{i:02d}",
                description="توضیحات تست " * 5,
            )
            PropertyImage.objects.create(property=prop, image=_png_upload(f"qc-{i}.png"))
            FollowUp.objects.create(
                title=f"پیگیری {i}",
                follow_up_type="VIEWING",
                consultant=self.agent,
                property=prop,
            )
            Task.objects.create(
                title=f"وظیفه {i}",
                task_type="VIEWING",
                status="PENDING",
                priority="MEDIUM",
                assigned_to=self.agent,
                created_by=self.agent,
                property=prop,
                due_date=timezone.now().date(),
            )

        large = self._list_query_count(100)

        self.assertLess(
            large,
            40,
            "the 100-row list must run a small constant number of queries",
        )
        self.assertLessEqual(large, small + 2)


class PropertyListConsultantScopeAllFilterTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="sa-admin", password="pw", role="ADMIN"
        )
        self.agent_a = User.objects.create_user(
            username="sa-agent-a", password="pw", role="AGENT"
        )
        self.agent_b = User.objects.create_user(
            username="sa-agent-b", password="pw", role="AGENT"
        )
        self.prop_a = _make_property(
            self.agent_a, title="ملک مشاور الف", internal_code="ZF_3001"
        )
        self.prop_b = _make_property(
            self.agent_b, title="ملک مشاور بی", internal_code="ZF_3002"
        )

    def test_consultant_scope_all_can_filter_by_consultant(self):
        client = APIClient()
        client.force_authenticate(user=self.agent_a)
        res = client.get(
            "/properties/api/properties/",
            {"scope": "all", "consultantId": self.agent_b.id, "page_size": 10},
        )
        self.assertEqual(res.status_code, 200)
        rows = res.json()["results"]
        self.assertEqual([r["id"] for r in rows], [self.prop_b.id])

    def test_consultant_without_scope_all_still_ignores_consultant_id(self):
        client = APIClient()
        client.force_authenticate(user=self.agent_a)
        res = client.get(
            "/properties/api/properties/",
            {"consultantId": self.agent_b.id, "page_size": 10},
        )
        self.assertEqual(res.status_code, 200)
        rows = res.json()["results"]
        self.assertEqual([r["id"] for r in rows], [self.prop_a.id])

    def test_admin_consultant_filter_still_works(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.get(
            "/properties/api/properties/",
            {"consultantId": self.agent_a.id, "page_size": 10},
        )
        self.assertEqual(res.status_code, 200)
        rows = res.json()["results"]
        self.assertEqual([r["id"] for r in rows], [self.prop_a.id])


class PropertyListPageSizeGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.listings.models import Listing

        agent = User.objects.create_user(
            username="guard-agent", password="pw", role="AGENT"
        )
        Property.objects.bulk_create(
            [
                Property(
                    title=f"ملک گارد {i}",
                    internal_code=f"ZF_8{i:03d}",
                    consultant=agent,
                    property_type="APARTMENT",
                    deal_type="SALE",
                    area=90,
                    address=f"آدرس {i}",
                )
                for i in range(120)
            ]
        )

    def test_page_size_is_clamped_to_100(self):
        client = APIClient()
        admin = User.objects.create_user(
            username="guard-admin", password="pw", role="ADMIN"
        )
        client.force_authenticate(user=admin)

        res = client.get("/properties/api/properties/", {"page_size": 1000})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["results"]), 100)
        self.assertEqual(data["count"], 120)

        res = client.get(
            "/properties/api/properties/", {"page_size": 100, "page": 2}
        )
        self.assertEqual(len(res.json()["results"]), 20)
