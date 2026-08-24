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


class FollowUpScheduledDateRangeApiTests(TestCase):
    """Server-side inclusive scheduled-date range (Asia/Tehran day boundaries)."""

    @classmethod
    def setUpTestData(cls):
        from apps.accounts.models import UserRole

        cls.admin = User.objects.create_user(
            username="fu_range_admin", password="pw", role=UserRole.ADMIN
        )
        cls.agent = User.objects.create_user(
            username="fu_range_agent", password="pw", role=UserRole.AGENT
        )
        cls.stranger = User.objects.create_user(
            username="fu_range_stranger", password="pw", role=UserRole.AGENT
        )
        cls.prop = Property.objects.create(
            title="ملک بازه",
            internal_code="FU-RANGE",
            consultant=cls.agent,
            area=80,
            address="تهران",
        )

        def fu(title, scheduled_at, follow_type=FollowUpType.CALL):
            return FollowUp.objects.create(
                title=title,
                follow_up_type=follow_type,
                consultant=cls.agent,
                contact_name="مخاطب",
                property=cls.prop,
                scheduled_at=scheduled_at,
                status=FollowUpStatus.SCHEDULED,
            )

        tehran = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
        # The five distinct Tehran calendar days around the range.
        cls.before = fu(
            "قبل", datetime.datetime(2026, 7, 15, 12, 0, tzinfo=tehran)
        )
        # Exactly the start of 2026-07-16 Tehran (00:00 local == 20:30 UTC prev day).
        cls.start_edge = fu(
            "لبه شروع", datetime.datetime(2026, 7, 16, 0, 0, tzinfo=tehran)
        )
        cls.mid = fu(
            "وسط", datetime.datetime(2026, 7, 17, 15, 30, tzinfo=tehran)
        )
        # Last instant of 2026-07-18 Tehran (23:59 local).
        cls.end_edge = fu(
            "لبه پایان", datetime.datetime(2026, 7, 18, 23, 59, tzinfo=tehran)
        )
        cls.after = fu(
            "بعد", datetime.datetime(2026, 7, 19, 9, 0, tzinfo=tehran)
        )
        # Another consultant's follow-up *inside* the July range. Admins can
        # see it (proving the endpoint is not globally restricted), but a
        # consultant-scoped query and the stranger's own query must behave.
        cls.other = FollowUp.objects.create(
            title="غریبه",
            follow_up_type=FollowUpType.EMAIL,
            consultant=cls.stranger,
            contact_name="غریبه",
            scheduled_at=datetime.datetime(2026, 7, 17, 10, 0, tzinfo=tehran),
            status=FollowUpStatus.SCHEDULED,
        )

    def setUp(self):
        self.client = APIClient()

    def _ids(self, resp):
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        payload = resp.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        return {row["id"] for row in rows}

    def test_inclusive_tehran_day_boundaries(self):
        self.client.force_authenticate(user=self.admin)
        ids = self._ids(
            self.client.get(
                "/followupa/api/followups/?consultantId=%s&scheduledDateFrom=2026-07-16&scheduledDateTo=2026-07-18"
                % self.agent.id
            )
        )
        self.assertEqual(
            ids,
            {self.start_edge.id, self.mid.id, self.end_edge.id},
        )

    def test_midnight_tehran_boundary_is_local_day(self):
        """00:00 Tehran on the 16th serialises to the 15th in UTC; slicing the
        string would wrongly exclude it. The Asia/Tehran range must include it."""
        self.client.force_authenticate(user=self.admin)
        ids = self._ids(
            self.client.get(
                "/followupa/api/followups/?scheduledDateFrom=2026-07-16&scheduledDateTo=2026-07-16"
            )
        )
        self.assertEqual(ids, {self.start_edge.id})

    def test_from_only(self):
        self.client.force_authenticate(user=self.admin)
        ids = self._ids(
            self.client.get(
                "/followupa/api/followups/?consultantId=%s&scheduledDateFrom=2026-07-18"
                % self.agent.id
            )
        )
        self.assertEqual(ids, {self.end_edge.id, self.after.id})

    def test_to_only(self):
        self.client.force_authenticate(user=self.admin)
        ids = self._ids(
            self.client.get(
                "/followupa/api/followups/?consultantId=%s&scheduledDateTo=2026-07-16"
                % self.agent.id
            )
        )
        self.assertEqual(ids, {self.before.id, self.start_edge.id})

    def test_outside_range_excluded(self):
        self.client.force_authenticate(user=self.admin)
        ids = self._ids(
            self.client.get(
                "/followupa/api/followups/?consultantId=%s&scheduledDateFrom=2026-08-01&scheduledDateTo=2026-08-02"
                % self.agent.id
            )
        )
        self.assertEqual(ids, set())

    def test_combines_with_type_filter(self):
        self.client.force_authenticate(user=self.admin)
        # Make mid an Email; a Call-only range must drop it.
        self.mid.follow_up_type = FollowUpType.EMAIL
        self.mid.save()
        ids = self._ids(
            self.client.get(
                "/followupa/api/followups/?consultantId=%s&scheduledDateFrom=2026-07-16&scheduledDateTo=2026-07-18&type=Call"
                % self.agent.id
            )
        )
        self.assertEqual(ids, {self.start_edge.id, self.end_edge.id})

    def test_consultant_scope_is_enforced(self):
        self.client.force_authenticate(user=self.agent)
        ids = self._ids(
            self.client.get(
                "/followupa/api/followups/?scheduledDateFrom=2026-07-16&scheduledDateTo=2026-07-18"
            )
        )
        self.assertNotIn(self.other.id, ids)
        self.assertEqual(
            ids,
            {self.start_edge.id, self.mid.id, self.end_edge.id},
        )

    def test_stranger_sees_only_own(self):
        self.client.force_authenticate(user=self.stranger)
        ids = self._ids(
            self.client.get(
                "/followupa/api/followups/?scheduledDateFrom=2026-07-01&scheduledDateTo=2026-07-31"
            )
        )
        self.assertEqual(ids, {self.other.id})

    def test_invalid_date_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get("/followupa/api/followups/?scheduledDateFrom=not-a-date")
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("scheduledDateFrom", resp.json())

    def test_reversed_range_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(
            "/followupa/api/followups/?scheduledDateFrom=2026-07-20&scheduledDateTo=2026-07-18"
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertIn("scheduledDateFrom", body)
        self.assertIn("scheduledDateTo", body)
