import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.followups.models import FollowUp, FollowUpStatus, FollowUpType
from apps.properties.models import Property

User = get_user_model()


class FollowUpEditApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="fu-admin", password="pw", role="ADMIN")
        self.agent = User.objects.create_user(username="fu-agent", password="pw", role="AGENT")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.prop = Property.objects.create(
            title="ملک پیگیری",
            internal_code="FU-1",
            consultant=self.agent,
            area=90,
            address="تهران",
        )
        self.followup = FollowUp.objects.create(
            title="تماس اولیه",
            follow_up_type=FollowUpType.CALL,
            consultant=self.agent,
            contact_name="علی رضایی",
            property=self.prop,
            scheduled_at=timezone.now(),
            notes="یادداشت اول",
            status=FollowUpStatus.SCHEDULED,
        )

    def test_patch_updates_followup_fields(self):
        new_date = (timezone.now() + datetime.timedelta(days=2)).isoformat()
        resp = self.client.patch(
            f"/followupa/api/followups/{self.followup.id}/",
            {
                "title": "تماس پیگیری ویرایش‌شده",
                "type": "Meeting",
                "contact": "مریم احمدی",
                "date": new_date,
                "consultantId": self.agent.id,
                "propertyId": self.prop.id,
                "notes": "یادداشت جدید",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        data = resp.json()
        self.assertEqual(data["title"], "تماس پیگیری ویرایش‌شده")
        self.assertEqual(data["type"], "Meeting")
        self.assertEqual(data["contact"], "مریم احمدی")
        self.assertEqual(data["notes"], "یادداشت جدید")
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.title, "تماس پیگیری ویرایش‌شده")
        self.assertEqual(self.followup.follow_up_type, FollowUpType.MEETING)
        self.assertEqual(self.followup.contact_name, "مریم احمدی")
        self.assertEqual(self.followup.status, FollowUpStatus.SCHEDULED)

    def test_consultant_can_patch_own_followup(self):
        agent_client = APIClient()
        agent_client.force_authenticate(user=self.agent)
        resp = agent_client.patch(
            f"/followupa/api/followups/{self.followup.id}/",
            {"title": "ویرایش مشاور", "notes": "توسط مشاور"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.title, "ویرایش مشاور")
        self.assertEqual(self.followup.notes, "توسط مشاور")


    def test_patch_does_not_reset_completed_status(self):
        """Omitting status on PATCH must not flip a completed follow-up back to scheduled."""
        self.followup.status = FollowUpStatus.COMPLETED
        self.followup.outcome = "نتیجه ثبت شد"
        self.followup.save()
        resp = self.client.patch(
            f"/followupa/api/followups/{self.followup.id}/",
            {"title": "عنوان بعد از تکمیل", "notes": "فقط عنوان"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.title, "عنوان بعد از تکمیل")
        self.assertEqual(self.followup.status, FollowUpStatus.COMPLETED)
        self.assertEqual(self.followup.outcome, "نتیجه ثبت شد")


    def test_list_filter_by_consultant_and_property(self):
        other_agent = User.objects.create_user(username="fu-agent-2", password="pw", role="AGENT")
        other_prop = Property.objects.create(
            title="ملک دیگر",
            internal_code="FU-2",
            consultant=other_agent,
            area=70,
            address="ساری",
        )
        other = FollowUp.objects.create(
            title="پیگیری مشاور دیگر",
            follow_up_type=FollowUpType.EMAIL,
            consultant=other_agent,
            contact_name="سارا",
            property=other_prop,
            scheduled_at=timezone.now(),
            status=FollowUpStatus.SCHEDULED,
        )

        def _ids(resp):
            payload = resp.json()
            rows = payload["results"] if isinstance(payload, dict) else payload
            return [row["id"] for row in rows]

        by_consultant = self.client.get(f"/followupa/api/followups/?consultantId={self.agent.id}")
        self.assertEqual(by_consultant.status_code, 200, by_consultant.content[:300])
        consultant_ids = _ids(by_consultant)
        self.assertIn(self.followup.id, consultant_ids)
        self.assertNotIn(other.id, consultant_ids)

        by_property = self.client.get(f"/followupa/api/followups/?propertyId={self.prop.id}")
        self.assertEqual(by_property.status_code, 200, by_property.content[:300])
        property_ids = _ids(by_property)
        self.assertIn(self.followup.id, property_ids)
        self.assertNotIn(other.id, property_ids)

        both = self.client.get(
            f"/followupa/api/followups/?consultantId={self.agent.id}&propertyId={self.prop.id}"
        )
        self.assertEqual(both.status_code, 200)
        both_ids = _ids(both)
        self.assertEqual(both_ids, [self.followup.id])


class FollowUpOrderingTests(TestCase):
    """Follow-ups must be returned newest-activity-first: a follow-up that
    was created or edited most recently appears at the top of the list and
    of the dashboard widget, and the order updates dynamically."""

    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(
            username="fu-order-agent", password="pw", role="AGENT"
        )

    def _create(self, title, scheduled_offset_days, created_at=None, updated_at=None):
        followup = FollowUp.objects.create(
            title=title,
            consultant=self.agent,
            contact_name="مخاطب تست",
            scheduled_at=timezone.now() + datetime.timedelta(days=scheduled_offset_days),
        )
        # Fix the timestamps explicitly so the ordering is deterministic
        # regardless of how fast the test database executes.
        if created_at is not None or updated_at is not None:
            FollowUp.objects.filter(pk=followup.pk).update(
                created_at=created_at or followup.created_at,
                updated_at=updated_at or followup.updated_at,
            )
        followup.refresh_from_db()
        return followup

    def _list_ids(self, client, query=""):
        resp = client.get(f"/followupa/api/followups/{query}")
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        payload = resp.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        return [row["id"] for row in rows]

    def test_list_orders_newest_created_first(self):
        base = timezone.now() - datetime.timedelta(hours=1)
        older = self._create("قدیمی‌تر", 1, created_at=base, updated_at=base)
        newer = self._create(
            "جدیدتر", 2, created_at=base + datetime.timedelta(minutes=1),
            updated_at=base + datetime.timedelta(minutes=1),
        )

        client = APIClient()
        client.force_authenticate(user=self.agent)
        ids = self._list_ids(client)
        self.assertEqual(ids[0], newer.id)
        self.assertEqual(ids[1], older.id)

    def test_editing_moves_followup_to_top(self):
        base = timezone.now() - datetime.timedelta(hours=1)
        first = self._create("اول", 1, created_at=base, updated_at=base)
        second = self._create(
            "دوم", 2, created_at=base + datetime.timedelta(minutes=1),
            updated_at=base + datetime.timedelta(minutes=1),
        )

        client = APIClient()
        client.force_authenticate(user=self.agent)
        self.assertEqual(self._list_ids(client)[0], second.id)

        # Editing the older follow-up must re-order the list dynamically.
        resp = client.patch(
            f"/followupa/api/followups/{first.id}/",
            {"title": "اول (ویرایش‌شده)"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertTrue(resp.json().get("updatedAt"))
        ids = self._list_ids(client)
        self.assertEqual(ids[0], first.id)
        self.assertEqual(ids[1], second.id)

    def test_newer_created_wins_even_when_scheduled_earlier(self):
        """Scheduled time must not decide the order: a follow-up created
        later surfaces first even if it is scheduled earlier."""
        base = timezone.now() - datetime.timedelta(hours=1)
        created_first = self._create(
            "اول", 5, created_at=base, updated_at=base
        )
        created_second = self._create(
            "دوم", 1, created_at=base + datetime.timedelta(minutes=1),
            updated_at=base + datetime.timedelta(minutes=1),
        )

        client = APIClient()
        client.force_authenticate(user=self.agent)
        ids = self._list_ids(client)
        self.assertEqual(ids[0], created_second.id)
        self.assertEqual(ids[1], created_first.id)

    def test_explicit_ordering_param_still_works(self):
        base = timezone.now() - datetime.timedelta(hours=1)
        earlier = self._create("زودتر", 1, created_at=base, updated_at=base)
        later = self._create(
            "دیرتر", 3, created_at=base + datetime.timedelta(minutes=1),
            updated_at=base + datetime.timedelta(minutes=1),
        )

        client = APIClient()
        client.force_authenticate(user=self.agent)
        ids = self._list_ids(client, "?ordering=scheduled_at")
        self.assertEqual(ids[0], earlier.id)
        self.assertEqual(ids[1], later.id)

    def test_model_default_ordering_is_newest_activity_first(self):
        base = timezone.now() - datetime.timedelta(hours=1)
        older = self._create("قدیمی", 1, created_at=base, updated_at=base)
        newer = self._create(
            "جدید", 2, created_at=base + datetime.timedelta(minutes=1),
            updated_at=base + datetime.timedelta(minutes=1),
        )
        ids = list(FollowUp.objects.values_list("id", flat=True))
        self.assertEqual(ids[0], newer.id)
        self.assertIn(older.id, ids)
