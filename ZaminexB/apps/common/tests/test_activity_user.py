from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.common.activity import log_activity
from apps.common.models import ActivityLog
from apps.common.thread_locals import set_current_user, clear_current_user

User = get_user_model()


class ActivityLogUserTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_test",
            password="pwd",
            role="ADMIN",
        )
        self.consultant_user = User.objects.create_user(
            username="consultant_test",
            password="pwd",
            role="AGENT",
        )

    def tearDown(self):
        clear_current_user()

    def test_log_activity_uses_current_user(self):
        set_current_user(self.admin_user)
        log_activity(
            user=self.consultant_user,
            action="update",
            target_type="property",
            target_id=10,
            description="ویرایش ملک توسط ادمین",
        )
        log = ActivityLog.objects.latest("id")
        self.assertEqual(log.user, self.admin_user)

    def test_log_activity_fallback_when_no_current_user(self):
        clear_current_user()
        log_activity(
            user=self.consultant_user,
            action="update",
            target_type="property",
            target_id=11,
            description="ویرایش ملک در پس‌زمینه",
        )
        log = ActivityLog.objects.latest("id")
        self.assertEqual(log.user, self.consultant_user)

    def test_update_signal_creates_update_activity_log(self):
        from apps.properties.models import Property
        set_current_user(self.admin_user)
        prop = Property.objects.create(
            title="ملک اولیه",
            internal_code="P-999",
            consultant=self.consultant_user,
            area=100,
            address="آدرس اولیه",
        )

        # Clear logs from creation
        ActivityLog.objects.all().delete()

        # Update property
        prop.title = "ملک جدید ویرایش‌شده"
        prop.save()

        logs = ActivityLog.objects.filter(target_type="property", action="update")
        self.assertEqual(logs.count(), 1)
        self.assertIn("ویرایش شد", logs.first().description)

    def test_delete_all_activity_logs_api(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        ActivityLog.objects.create(
            user=self.admin_user,
            action="create",
            target_type="system",
            target_id=1,
            description="تست لاگ ۱",
        )

        resp = client.delete("/common/api/activity-log/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ActivityLog.objects.count(), 0)

