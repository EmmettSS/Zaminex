import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.common.models import ActivityLog
from apps.common.thread_locals import clear_current_user, set_current_user
from apps.tasks.history import task_history_items
from apps.tasks.models import Task

User = get_user_model()


class TaskHistoryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="hist_admin",
            password="pass12345",
            first_name="سارا",
            last_name="مدیری",
            role=UserRole.ADMIN,
        )
        self.agent = User.objects.create_user(
            username="hist_agent",
            password="pass12345",
            first_name="علی",
            last_name="مشاوری",
            role=UserRole.AGENT,
        )
        self.other = User.objects.create_user(
            username="hist_other",
            password="pass12345",
            first_name="رضا",
            last_name="غریبه",
            role=UserRole.AGENT,
        )
        self.client = APIClient()

    def tearDown(self):
        clear_current_user()

    def _create_task(self, **kwargs):
        defaults = {
            "title": "بازدید ملک ساری",
            "assigned_to": self.agent,
            "created_by": self.admin,
            "due_date": datetime.date.today() + datetime.timedelta(days=3),
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
        }
        defaults.update(kwargs)
        return Task.objects.create(**defaults)

    def test_create_logs_actor_and_title(self):
        set_current_user(self.admin)
        task = self._create_task()
        logs = ActivityLog.objects.filter(target_type="task", target_id=task.pk)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.action, ActivityLog.ActionType.CREATE)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.metadata.get("event_title"), "ایجاد وظیفه")
        self.assertIn("ایجاد شد", log.description)

    def test_status_change_records_actor_from_to_and_persian_title(self):
        set_current_user(self.admin)
        task = self._create_task()
        ActivityLog.objects.all().delete()

        set_current_user(self.agent)
        task.status = Task.Status.IN_PROGRESS
        task.save()

        log = ActivityLog.objects.get(target_type="task", target_id=task.pk)
        self.assertEqual(log.action, ActivityLog.ActionType.STATUS_CHANGE)
        self.assertEqual(log.user, self.agent)
        self.assertEqual(log.metadata.get("event_title"), "تغییر وضعیت")
        changes = log.metadata.get("changes") or []
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["fromLabel"], "در انتظار انجام")
        self.assertEqual(changes[0]["toLabel"], "در حال انجام")

    def test_complete_and_reassign_use_current_user_not_assignee(self):
        set_current_user(self.admin)
        task = self._create_task()
        ActivityLog.objects.all().delete()

        set_current_user(self.admin)
        task.status = Task.Status.COMPLETED
        task.assigned_to = self.other
        task.save()

        log = ActivityLog.objects.get(target_type="task", target_id=task.pk)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.action, ActivityLog.ActionType.COMPLETE)
        fields = {c["field"] for c in log.metadata.get("changes") or []}
        self.assertIn("status", fields)
        self.assertIn("assigned_to_id", fields)

    def test_no_log_when_nothing_meaningful_changed(self):
        set_current_user(self.admin)
        task = self._create_task()
        ActivityLog.objects.all().delete()
        task.save()
        self.assertEqual(ActivityLog.objects.filter(target_type="task", target_id=task.pk).count(), 0)

    def test_history_payload_has_date_title_and_user(self):
        set_current_user(self.admin)
        task = self._create_task()
        set_current_user(self.agent)
        task.status = Task.Status.CANCELLED
        task.save()

        items = task_history_items(task)
        self.assertGreaterEqual(len(items), 2)
        cancel = next(i for i in items if i["action"] == ActivityLog.ActionType.ARCHIVE)
        self.assertEqual(cancel["title"], "لغو وظیفه")
        self.assertEqual(cancel["user"], "علی مشاوری")
        self.assertTrue(cancel["createdAt"])
        self.assertEqual(cancel["from"], "در انتظار انجام")
        self.assertEqual(cancel["to"], "لغوشده")

    def test_history_synthesizes_create_when_log_missing(self):
        set_current_user(self.admin)
        task = self._create_task()
        ActivityLog.objects.all().delete()
        items = task_history_items(task)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "ایجاد وظیفه")
        self.assertEqual(items[0]["user"], "سارا مدیری")
        self.assertTrue(items[0]["createdAt"])


class TaskHistoryAPITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="hist_api_admin",
            password="pass12345",
            first_name="مینا",
            last_name="ادمین",
            role=UserRole.ADMIN,
        )
        self.agent = User.objects.create_user(
            username="hist_api_agent",
            password="pass12345",
            first_name="حسین",
            last_name="مشاور",
            role=UserRole.AGENT,
        )
        self.stranger = User.objects.create_user(
            username="hist_api_stranger",
            password="pass12345",
            role=UserRole.AGENT,
        )
        self.client = APIClient()

    def tearDown(self):
        clear_current_user()

    def test_api_create_and_patch_history_uses_request_user(self):
        self.client.force_authenticate(user=self.admin)
        create = self.client.post(
            "/tasks/api/tasks/",
            {
                "title": "هماهنگی قرارداد",
                "due_date": str(datetime.date.today() + datetime.timedelta(days=5)),
                "assigned_to": self.agent.id,
                "priority": "HIGH",
                "status": "PENDING",
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.content)
        task_id = create.json()["id"]

        self.client.force_authenticate(user=self.agent)
        patch = self.client.patch(
            f"/tasks/api/tasks/{task_id}/",
            {"status": "IN_PROGRESS"},
            format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.content)

        self.client.force_authenticate(user=self.admin)
        hist = self.client.get(f"/tasks/api/tasks/{task_id}/history/")
        self.assertEqual(hist.status_code, 200)
        rows = hist.json()["results"]
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(row.get("createdAt") and row.get("user") and row.get("title") for row in rows))
        create_row = next(r for r in rows if r["action"] == "create")
        status_row = next(r for r in rows if r["action"] == "status_change")
        self.assertEqual(create_row["user"], "مینا ادمین")
        self.assertEqual(create_row["title"], "ایجاد وظیفه")
        self.assertEqual(status_row["user"], "حسین مشاور")
        self.assertEqual(status_row["from"], "در انتظار انجام")
        self.assertEqual(status_row["to"], "در حال انجام")

    def test_assignee_can_read_history_stranger_cannot(self):
        self.client.force_authenticate(user=self.admin)
        create = self.client.post(
            "/tasks/api/tasks/",
            {
                "title": "بازرسی فنی",
                "due_date": str(datetime.date.today() + datetime.timedelta(days=2)),
                "assigned_to": self.agent.id,
                "status": "PENDING",
            },
            format="json",
        )
        task_id = create.json()["id"]

        self.client.force_authenticate(user=self.agent)
        ok = self.client.get(f"/tasks/api/tasks/{task_id}/history/")
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["results"])

        self.client.force_authenticate(user=self.stranger)
        denied = self.client.get(f"/tasks/api/tasks/{task_id}/history/")
        self.assertEqual(denied.status_code, 404)

    def test_note_can_be_saved_and_returned(self):
        self.client.force_authenticate(user=self.admin)
        create = self.client.post(
            "/tasks/api/tasks/",
            {
                "title": "وظیفه با یادداشت",
                "due_date": str(datetime.date.today() + datetime.timedelta(days=1)),
                "assigned_to": self.agent.id,
                "status": "PENDING",
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.content)
        task_id = create.json()["id"]

        patch = self.client.patch(
            f"/tasks/api/tasks/{task_id}/",
            {"note": "یادداشت تستی برای این وظیفه"},
            format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.content)
        self.assertEqual(patch.json()["note"], "یادداشت تستی برای این وظیفه")

        detail = self.client.get(f"/tasks/api/tasks/{task_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["note"], "یادداشت تستی برای این وظیفه")
