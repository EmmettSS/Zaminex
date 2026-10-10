from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.activity.labels import translate_description
from apps.activity.models import ActivityLog

User = get_user_model()

_PROPERTY_TOKENS = ("AVAILABLE", "RESERVED", "SOLD", "INACTIVE", "Available", "Reserved", "Sold", "Archived")
_LISTING_TOKENS = ("ACTIVE", "DRAFT", "PAUSED", "SOLD", "EXPIRED", "ARCHIVED", "Active", "Draft", "Paused", "Sold", "Expired", "Archived")
_TASK_TOKENS = ("PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED", "Pending", "In Progress", "Completed", "Cancelled")


class NewRowPersianStatusTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="fa-adm", password="pw", role="ADMIN")
        self.agent = User.objects.create_user(username="fa-ag", password="pw", role="AGENT")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _property(self):
        from apps.properties.models import Property

        return Property.objects.create(
            title="ملک تست",
            internal_code="FA-1",
            consultant=self.agent,
            property_type="APARTMENT",
            deal_type="SALE",
            area=80,
            address="ساری",
        )

    def test_property_status_change_is_persian(self):
        prop = self._property()
        ActivityLog.objects.all().delete()

        resp = self.client.patch(
            f"/properties/api/properties/{prop.id}/",
            {"status": "RESERVED"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])

        log = ActivityLog.objects.get(target_type="property", action="status_change")
        self.assertIn("آماده واگذاری", log.description)
        self.assertIn("رزرو شده", log.description)
        self.assertIn("ملک تست", log.description)
        for token in _PROPERTY_TOKENS:
            self.assertNotIn(token, log.description)

    def test_listing_status_change_is_persian(self):
        from apps.listings.models import Listing

        prop = self._property()
        listing = Listing.objects.create(
            property=prop,
            title="آگهی تست",
            publish_channel="WEBSITE",
            created_by=self.agent,
        )
        ActivityLog.objects.all().delete()

        listing.status = Listing.Status.SOLD
        listing.save()

        log = ActivityLog.objects.get(target_type="listing", action="complete")
        self.assertIn("فروخته‌شده", log.description)
        self.assertIn("آگهی تست", log.description)
        for token in _LISTING_TOKENS:
            self.assertNotIn(token, log.description)

    def test_task_status_change_is_persian(self):
        from apps.tasks.models import Task

        task = Task.objects.create(
            title="وظیفه تست",
            created_by=self.agent,
            assigned_to=self.agent,
            due_date=timezone.now().date() + timedelta(days=3),
        )
        ActivityLog.objects.all().delete()

        task.status = Task.Status.IN_PROGRESS
        task.save()

        log = ActivityLog.objects.get(target_type="task", action="status_change")
        self.assertIn("در حال انجام", log.description)
        self.assertIn("وظیفه تست", log.description)
        for token in _TASK_TOKENS:
            self.assertNotIn(token, log.description)

    def test_followup_status_change_is_persian(self):
        from apps.followups.models import FollowUp

        fu = FollowUp.objects.create(
            title="پیگیری تست",
            contact_name="مشتری",
            consultant=self.agent,
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        ActivityLog.objects.all().delete()

        fu.status = "completed"
        fu.save()

        log = ActivityLog.objects.get(target_type="followup", action="complete")
        self.assertEqual(log.description, "پیگیری «پیگیری تست» تکمیل شد")
        for token in ("completed", "Completed", "scheduled", "Scheduled"):
            self.assertNotIn(token, log.description)


class LegacyRowRenderTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="lg-adm", password="pw", role="ADMIN")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _descriptions(self):
        resp = self.client.get("/common/api/activity-log/")
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        data = resp.json()
        rows = data["results"] if isinstance(data, dict) else data
        return [row["description"] for row in rows]

    def test_legacy_property_status_row_renders_persian(self):
        ActivityLog.objects.create(
            user=self.admin,
            action="status_change",
            target_type="property",
            target_id=1,
            description="وضعیت ملک «X» از AVAILABLE به RESERVED تغییر کرد",
        )
        descriptions = self._descriptions()
        self.assertIn("وضعیت ملک «X» از آماده واگذاری به رزرو شده تغییر کرد", descriptions)
        for token in _PROPERTY_TOKENS:
            self.assertNotIn(token, "\n".join(descriptions))

    def test_legacy_listing_status_row_renders_persian(self):
        ActivityLog.objects.create(
            user=self.admin,
            action="complete",
            target_type="listing",
            target_id=1,
            description="وضعیت آگهی «X» به Sold تغییر کرد",
        )
        descriptions = self._descriptions()
        self.assertIn("وضعیت آگهی «X» به فروخته‌شده تغییر کرد", descriptions)
        for token in _LISTING_TOKENS:
            self.assertNotIn(token, "\n".join(descriptions))


class TranslateDescriptionUnitTests(TestCase):
    def test_unknown_token_passes_through(self):
        self.assertEqual(
            translate_description("وضعیت ملک «X» از MYSTERY به RESERVED تغییر کرد", "property"),
            "وضعیت ملک «X» از MYSTERY به رزرو شده تغییر کرد",
        )

    def test_data_values_are_preserved(self):
        desc = "وضعیت ملک «X» (کد ZF_100) از AVAILABLE به INACTIVE تغییر کرد"
        out = translate_description(desc, "property")
        self.assertIn("ZF_100", out)
        self.assertIn("«X»", out)
        self.assertNotIn("AVAILABLE", out)
        self.assertNotIn("INACTIVE", out)

    def test_non_status_description_is_untouched(self):
        desc = "پیگیری «ملک قسطی» برای علی ایجاد شد"
        self.assertEqual(translate_description(desc, "followup"), desc)

    def test_other_target_type_is_untouched(self):
        self.assertEqual(
            translate_description("خروجی فهرست تیکت‌ها دریافت شد", "system"),
            "خروجی فهرست تیکت‌ها دریافت شد",
        )
