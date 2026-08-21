import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ConsultantProfile, UserRole
from apps.common.analytics_views import consultant_detail_report
from apps.common.metrics import (
    consultant_followups_overdue_count,
    consultant_performance_metrics,
    consultant_tasks_overdue_count,
)
from apps.followups.models import FollowUp, FollowUpStatus
from apps.followups.serializers import FollowUpListSerializer
from apps.properties.models import Property
from apps.reports.services import compute_property_report
from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer

User = get_user_model()


class OverdueFlagTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="overdue_agent", password="pass12345", role=UserRole.AGENT
        )
        self.profile = ConsultantProfile.objects.create(
            user=self.agent, full_name="Overdue Agent", branch="مرکزی"
        )
        self.prop = Property.objects.create(
            title="Overdue Prop",
            internal_code="OV-1",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=100,
            area=80,
            rooms=2,
            address="addr",
            neighborhood="N",
        )

    def test_task_is_overdue_only_when_open_and_past_due(self):
        overdue = Task.objects.create(
            title="late",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() - datetime.timedelta(days=1),
            status=Task.Status.PENDING,
        )
        completed = Task.objects.create(
            title="done late",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() - datetime.timedelta(days=2),
            status=Task.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        cancelled = Task.objects.create(
            title="cancelled late",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() - datetime.timedelta(days=2),
            status=Task.Status.CANCELLED,
        )
        upcoming = Task.objects.create(
            title="soon",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() + datetime.timedelta(days=2),
            status=Task.Status.IN_PROGRESS,
        )
        self.assertTrue(overdue.is_overdue())
        self.assertFalse(completed.is_overdue())
        self.assertFalse(cancelled.is_overdue())
        self.assertFalse(upcoming.is_overdue())
        self.assertTrue(TaskSerializer(overdue).data["isOverdue"])
        self.assertFalse(TaskSerializer(completed).data["isOverdue"])

    def test_followup_is_overdue_only_when_scheduled_and_past(self):
        overdue = FollowUp.objects.create(
            title="late fu",
            consultant=self.agent,
            contact_name="c",
            property=self.prop,
            scheduled_at=timezone.now() - datetime.timedelta(days=1),
            status=FollowUpStatus.SCHEDULED,
        )
        completed = FollowUp.objects.create(
            title="done fu",
            consultant=self.agent,
            contact_name="c",
            property=self.prop,
            scheduled_at=timezone.now() - datetime.timedelta(days=1),
            status=FollowUpStatus.COMPLETED,
            outcome="ok",
        )
        upcoming = FollowUp.objects.create(
            title="soon fu",
            consultant=self.agent,
            contact_name="c",
            property=self.prop,
            scheduled_at=timezone.now() + datetime.timedelta(days=2),
            status=FollowUpStatus.SCHEDULED,
        )
        archived = FollowUp.objects.create(
            title="archived fu",
            consultant=self.agent,
            contact_name="c",
            property=self.prop,
            scheduled_at=timezone.now() - datetime.timedelta(days=3),
            status=FollowUpStatus.SCHEDULED,
            is_archived=True,
        )
        self.assertTrue(overdue.is_overdue())
        self.assertFalse(completed.is_overdue())
        self.assertFalse(upcoming.is_overdue())
        self.assertFalse(archived.is_overdue())
        self.assertTrue(FollowUpListSerializer(overdue).data["isOverdue"])
        self.assertFalse(FollowUpListSerializer(upcoming).data["isOverdue"])

    def test_consultant_and_property_analytics_count_overdue_followups(self):
        Task.objects.create(
            title="late task",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() - datetime.timedelta(days=1),
            status=Task.Status.PENDING,
        )
        FollowUp.objects.create(
            title="late fu",
            consultant=self.agent,
            contact_name="c",
            property=self.prop,
            scheduled_at=timezone.now() - datetime.timedelta(hours=3),
            status=FollowUpStatus.SCHEDULED,
        )
        FollowUp.objects.create(
            title="future fu",
            consultant=self.agent,
            contact_name="c",
            property=self.prop,
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
            status=FollowUpStatus.SCHEDULED,
        )

        self.assertEqual(consultant_tasks_overdue_count(self.agent), 1)
        self.assertEqual(consultant_followups_overdue_count(self.agent), 1)
        perf = consultant_performance_metrics(self.profile)
        self.assertEqual(perf["tasksOverdueCount"], 1)
        self.assertEqual(perf["followupsOverdueCount"], 1)

        report = compute_property_report(self.prop)
        self.assertEqual(report["kpis"]["tasksOverdueCount"], 1)
        self.assertEqual(report["kpis"]["followupsOverdueCount"], 1)
        self.assertTrue(
            any(row["count"] for row in report["charts"]["followupsOverdueByType"])
        )

        detail = consultant_detail_report(self.profile)
        self.assertEqual(detail["kpis"]["followupsOverdueCount"], 1)
        statuses = {row["status"]: row["count"] for row in detail["charts"]["followupsByStatus"]}
        self.assertEqual(statuses.get("overdue"), 1)
        self.assertEqual(statuses.get("scheduled"), 1)
        self.assertLess(detail["charts"]["performanceProfile"][1]["score"], 100)


class OverdueAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.agent = User.objects.create_user(
            username="overdue_api", password="pass12345", role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=self.agent, full_name="API Agent", branch="مرکزی"
        )
        self.client.force_authenticate(user=self.agent)

    def test_task_and_followup_list_expose_is_overdue(self):
        Task.objects.create(
            title="late api",
            assigned_to=self.agent,
            created_by=self.agent,
            due_date=datetime.date.today() - datetime.timedelta(days=1),
            status=Task.Status.PENDING,
        )
        FollowUp.objects.create(
            title="late api fu",
            consultant=self.agent,
            contact_name="c",
            scheduled_at=timezone.now() - datetime.timedelta(days=1),
            status=FollowUpStatus.SCHEDULED,
        )

        tasks = self.client.get("/tasks/api/tasks/")
        self.assertEqual(tasks.status_code, 200)
        task_items = tasks.json()
        if isinstance(task_items, dict):
            task_items = task_items.get("results", [])
        self.assertTrue(any(item.get("isOverdue") for item in task_items))

        followups = self.client.get("/followupa/api/followups/")
        self.assertEqual(followups.status_code, 200)
        fu_items = followups.json()
        if isinstance(fu_items, dict):
            fu_items = fu_items.get("results", [])
        self.assertTrue(any(item.get("isOverdue") for item in fu_items))
