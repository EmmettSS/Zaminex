import csv
import datetime
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ConsultantProfile, UserRole
from apps.followups.models import FollowUp
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task

from .services import compute_property_report, get_property_for_user_or_403

User = get_user_model()


class ReportsServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="ag", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=self.agent, full_name="Agent A", branch="B"
        )
        self.agent2 = User.objects.create_user(
            username="ag2", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=self.agent2, full_name="Agent B", branch="B"
        )
        self.prop = Property.objects.create(
            title="Apt 1",
            internal_code="R1",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("1000000000"),
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N1",
            latitude=Decimal("35.7"),
            longitude=Decimal("51.4"),
        )
        # comparable same neighborhood/type
        Property.objects.create(
            title="Apt 2",
            internal_code="R2",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("800000000"),
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N1",
        )
        Property.objects.create(
            title="Apt 3",
            internal_code="R3",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("900000000"),
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N1",
        )

        self.task_overdue = Task.objects.create(
            title="T1",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() - datetime.timedelta(days=3),
            task_type=Task.TaskType.VIEWING,
            status=Task.Status.PENDING,
        )
        self.task_done = Task.objects.create(
            title="T2",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() + datetime.timedelta(days=2),
            task_type=Task.TaskType.DOCUMENT,
            status=Task.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        self.followup = FollowUp.objects.create(
            title="F1",
            consultant=self.agent,
            contact_name="c1",
            property=self.prop,
            probability=60,
            scheduled_at=timezone.now() - datetime.timedelta(days=2),
        )
        self.listing = Listing.objects.create(
            property=self.prop,
            title="L1",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.agent,
            assigned_to=self.agent,
            start_date=timezone.now() - datetime.timedelta(days=5),
        )

    def test_property_kpis_and_scoping(self):
        r = compute_property_report(self.prop)
        self.assertEqual(r["property"]["id"], self.prop.pk)
        self.assertEqual(r["kpis"]["tasksOverdueCount"], 1)
        self.assertEqual(r["kpis"]["followupsOverdueCount"], 1)
        self.assertEqual(r["kpis"]["imagesCount"], 0)
        self.assertEqual(r["kpis"]["pricePerSqm"], 10_000_000.0)
        self.assertTrue(r["kpis"]["geoPrecisionFlag"])
        self.assertEqual(r["kpis"]["listingCount"], 1)
        self.assertIn("tenureHistogram", r["charts"])
        self.assertIn("priceMap", r["charts"])
        self.assertEqual(len(r["charts"]["priceMap"]), 1)
        self.assertIsNotNone(r["kpis"]["priceDeviationIndex"])

    def test_agent_cannot_access_other_agents_property(self):
        with self.assertRaises(Exception):
            get_property_for_user_or_403(self.agent2, self.prop.pk)
        # self.agent can access
        p = get_property_for_user_or_403(self.agent, self.prop.pk)
        self.assertEqual(p.pk, self.prop.pk)
        # admin can access
        p2 = get_property_for_user_or_403(self.admin, self.prop.pk)
        self.assertEqual(p2.pk, self.prop.pk)

    def test_empty_state_no_listings_tasks_followups(self):
        prop2 = Property.objects.create(
            title="Bare",
            internal_code="R4",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.RENT,
            price=Decimal("0"),
            area=0,
            rooms=0,
            address="addr",
            neighborhood="Far",
        )
        r = compute_property_report(prop2)
        self.assertIsNone(r["kpis"]["pricePerSqm"])
        self.assertIsNone(r["kpis"]["priceDeviationIndex"])
        self.assertIsNone(r["kpis"]["listingBurnRate"])
        self.assertEqual(r["kpis"]["tasksOverdueCount"], 0)
        self.assertEqual(r["kpis"]["followupsOverdueCount"], 0)
        self.assertTrue(len(r["warnings"]) >= 1)
        self.assertEqual(r["charts"]["priceMap"], [])


class ReportsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="adm2", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="ag3", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=self.agent, full_name="A", branch="B"
        )
        self.prop = Property.objects.create(
            title="P",
            internal_code="M-1",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("500000000"),
            area=50,
            rooms=1,
            address="addr",
            neighborhood="N",
            latitude=Decimal("35.7"),
            longitude=Decimal("51.4"),
        )

    def test_auth_required(self):
        url = f"/api/reports/properties/{self.prop.pk}/"
        res = self.client.get(url)
        self.assertIn(res.status_code, [401, 403])

    def test_agent_403_on_other_property(self):
        other = User.objects.create_user(
            username="ag4", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(user=other, full_name="X", branch="B")
        self.client.force_authenticate(user=other)
        url = f"/api/reports/properties/{self.prop.pk}/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

    def test_owner_can_fetch(self):
        self.client.force_authenticate(user=self.agent)
        url = f"/api/reports/properties/{self.prop.pk}/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("kpis", data)
        self.assertIn("charts", data)

    def test_csv_export_returns_csv(self):
        self.client.force_authenticate(user=self.agent)
        url = f"/api/reports/properties/{self.prop.pk}/export/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv; charset=utf-8")
        text = res.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        self.assertEqual(len(rows), 1)
        self.assertIn("شناسه ملک", rows[0])

    def test_csv_export_is_logged_in_activity(self):
        from apps.common.models import ActivityLog

        self.client.force_authenticate(user=self.agent)
        url = f"/api/reports/properties/{self.prop.pk}/export/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        entry = ActivityLog.objects.filter(
            action=ActivityLog.ActionType.EXPORT,
            target_type=ActivityLog.TargetType.PROPERTY,
            target_id=self.prop.pk,
        ).first()
        self.assertIsNotNone(entry, "CSV export must be recorded in the activity log")
        self.assertEqual(entry.user_id, self.agent.id)
        self.assertEqual(entry.metadata.get("format"), "csv")

    def test_scope_report_returns_metrics(self):
        self.client.force_authenticate(user=self.agent)
        res = self.client.get("/api/reports/scope/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["kpis"]["propertyCount"], 1)
