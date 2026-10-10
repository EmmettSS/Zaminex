from datetime import timedelta
from io import StringIO

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.activity.models import ActivityLog


def _make_log(description, created_at):
    entry = ActivityLog.objects.create(
        action="update",
        target_type="property",
        target_id=1,
        description=description,
    )
    ActivityLog.objects.filter(pk=entry.pk).update(created_at=created_at)
    return entry


EXPIRED_KEY = "expired0000000000000000000001"
VALID_KEY = "valid000000000000000000000001"


def _run(*args):
    out = StringIO()
    call_command("prune_history", *args, stdout=out)
    return out.getvalue()


class PruneHistoryTests(TestCase):
    def test_deletes_only_entries_older_than_the_cutoff(self):
        now = timezone.now()
        old = _make_log("قدیمی", now - timedelta(days=200))
        recent = _make_log("اخیر", now - timedelta(days=10))
        boundary = _make_log("مرزی", now - timedelta(days=179))

        output = _run("--days", "180")

        self.assertFalse(ActivityLog.objects.filter(pk=old.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(pk=recent.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(pk=boundary.pk).exists())
        self.assertIn("1 activity entries", output)

    def test_dry_run_deletes_nothing(self):
        _make_log("قدیمی", timezone.now() - timedelta(days=400))
        before = ActivityLog.objects.count()

        output = _run("--days", "180", "--dry-run")

        self.assertEqual(ActivityLog.objects.count(), before)
        self.assertIn("would delete", output)

    def test_deletes_in_more_than_one_batch(self):
        now = timezone.now()
        stale = now - timedelta(days=400)
        for index in range(7):
            _make_log(f"قدیمی {index}", stale)
        _make_log("اخیر", now)

        output = _run("--days", "180", "--batch-size", "3")

        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertIn("3 activity entries so far", output)
        self.assertIn("6 activity entries so far", output)
        self.assertIn("7 activity entries so far", output)

    def test_clears_expired_sessions_and_keeps_valid_ones(self):
        now = timezone.now()
        Session.objects.create(
            session_key=EXPIRED_KEY,
            session_data="x",
            expire_date=now - timedelta(hours=1),
        )
        Session.objects.create(
            session_key=VALID_KEY,
            session_data="x",
            expire_date=now + timedelta(hours=1),
        )

        output = _run("--days", "180")

        self.assertFalse(Session.objects.filter(session_key=EXPIRED_KEY).exists())
        self.assertTrue(Session.objects.filter(session_key=VALID_KEY).exists())
        self.assertIn("expired sessions", output)

    def test_reports_both_tables_even_when_there_is_nothing_to_do(self):
        output = _run("--days", "180")
        self.assertIn("Activity log:", output)
        self.assertIn("Sessions:", output)
        self.assertIn("Pruned 0 activity entries", output)


class PruneHistoryArgumentTests(TestCase):
    def test_rejects_a_negative_retention_period(self):
        with self.assertRaises(CommandError):
            call_command("prune_history", "--days", "-1")

    def test_rejects_a_zero_batch_size(self):
        with self.assertRaises(CommandError):
            call_command("prune_history", "--batch-size", "0")

    def test_a_zero_day_retention_is_allowed(self):
        _make_log("همه", timezone.now())
        _run("--days", "0")
        self.assertEqual(ActivityLog.objects.count(), 0)
