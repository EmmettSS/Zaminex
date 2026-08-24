"""Tests for the admin "filter by user" feature on the activity report.

Covers:
  * the ``user_id`` query parameter on ``/common/api/activity-log/``
    (user primary key, "system", "all", and invalid values),
  * the security boundary: non-admin callers must never be able to read
    another user's logs through the new parameter,
  * ``/common/api/activity-log/users/`` (admin-only user list with counts).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.common.models import ActivityLog

User = get_user_model()

ACTIVITY_URL = "/common/api/activity-log/"
USERS_URL = "/common/api/activity-log/users/"


def make_log(user=None, action="create", target_type="system"):
    return ActivityLog.objects.create(
        user=user,
        action=action,
        target_type=target_type,
        target_id=1,
        description="لاگ آزمایشی",
    )


class ActivityLogUserFilterTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="boss", password="pwd", role="ADMIN"
        )
        self.other_admin = User.objects.create_user(
            username="boss2", password="pwd", role="ADMIN"
        )
        self.agent = User.objects.create_user(
            username="agent1", password="pwd", role="AGENT"
        )
        self.agent2 = User.objects.create_user(
            username="agent2", password="pwd", role="AGENT"
        )
        self.client = APIClient()

    # ------------------------------------------------------------------
    #  user_id parameter on the activity list
    # ------------------------------------------------------------------

    def test_admin_filters_logs_by_user(self):
        self.client.force_authenticate(self.admin)
        make_log(self.agent)
        make_log(self.agent2)
        make_log(self.agent)

        data = self.client.get(f"{ACTIVITY_URL}?user_id={self.agent.pk}").json()

        self.assertEqual(data["count"], 2)
        self.assertEqual(data["summary"]["total"], 2)
        self.assertTrue(
            all(item["userId"] == self.agent.pk for item in data["results"])
        )

    def test_admin_filters_system_logs_with_system_value(self):
        self.client.force_authenticate(self.admin)
        make_log(user=None)
        make_log(self.agent)

        data = self.client.get(f"{ACTIVITY_URL}?user_id=system").json()

        self.assertEqual(data["count"], 1)
        self.assertIsNone(data["results"][0]["userId"])
        self.assertEqual(data["results"][0]["userName"], "سیستم")

    def test_user_id_all_means_no_filter(self):
        self.client.force_authenticate(self.admin)
        make_log(self.agent)
        make_log(self.agent2)

        data = self.client.get(f"{ACTIVITY_URL}?user_id=all").json()

        self.assertEqual(data["count"], 2)

    def test_user_filter_combines_with_action_filter(self):
        self.client.force_authenticate(self.admin)
        make_log(self.agent, action="create")
        make_log(self.agent, action="delete")

        data = self.client.get(
            f"{ACTIVITY_URL}?user_id={self.agent.pk}&action=create"
        ).json()

        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["action"], "create")

    def test_invalid_user_id_is_ignored(self):
        self.client.force_authenticate(self.admin)
        make_log(self.agent)
        make_log(self.agent2)

        resp = self.client.get(f"{ACTIVITY_URL}?user_id=not-a-number")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 2)

    def test_non_admin_cannot_read_other_users_logs_via_user_id(self):
        self.client.force_authenticate(self.agent)
        make_log(self.agent2)
        make_log(self.admin)

        data = self.client.get(f"{ACTIVITY_URL}?user_id={self.admin.pk}").json()

        self.assertEqual(data["count"], 0)

    def test_non_admin_default_scope_is_unchanged(self):
        self.client.force_authenticate(self.agent)
        make_log(self.agent)
        make_log(user=None)
        make_log(self.agent2)

        data = self.client.get(ACTIVITY_URL).json()

        # Own entries plus system entries only.
        self.assertEqual(data["count"], 2)
        self.assertIn(
            {item["userId"] for item in data["results"]},
            [{self.agent.pk, None}],
        )

    # ------------------------------------------------------------------
    #  /activity-log/users/ endpoint
    # ------------------------------------------------------------------

    def test_admin_sees_users_with_log_counts(self):
        self.client.force_authenticate(self.admin)
        make_log(self.agent)
        make_log(self.agent)
        make_log(self.other_admin)
        make_log(user=None)

        data = self.client.get(USERS_URL).json()

        self.assertEqual(data["systemCount"], 1)
        by_id = {item["id"]: item for item in data["users"]}
        self.assertEqual(set(by_id), {self.agent.pk, self.other_admin.pk})
        self.assertEqual(by_id[self.agent.pk]["logCount"], 2)
        self.assertEqual(by_id[self.agent.pk]["role"], "AGENT")
        self.assertEqual(by_id[self.agent.pk]["roleLabel"], "مشاور")
        self.assertEqual(by_id[self.other_admin.pk]["roleLabel"], "مدیر")
        # Users without any log must not be listed at all.
        self.assertNotIn(self.agent2.pk, by_id)

    def test_user_list_is_sorted_by_activity(self):
        self.client.force_authenticate(self.admin)
        make_log(self.agent)
        make_log(self.agent)
        make_log(self.agent2)

        data = self.client.get(USERS_URL).json()

        self.assertEqual(data["users"][0]["id"], self.agent.pk)
        self.assertEqual(data["users"][1]["id"], self.agent2.pk)

    def test_user_list_empty_when_no_logs(self):
        self.client.force_authenticate(self.admin)

        data = self.client.get(USERS_URL).json()

        self.assertEqual(data["users"], [])
        self.assertEqual(data["systemCount"], 0)

    def test_user_list_is_admin_only(self):
        self.client.force_authenticate(self.agent)

        resp = self.client.get(USERS_URL)

        self.assertEqual(resp.status_code, 403)

    def test_user_list_requires_authentication(self):
        resp = APIClient().get(USERS_URL)

        self.assertIn(resp.status_code, (401, 403))
