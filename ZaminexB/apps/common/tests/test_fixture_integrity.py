"""Guards for the database-migration tooling (phase 1).

These tests lock in the two behaviours that make a SQLite → PostgreSQL move
reproducible:

  * loading a fixture must not fabricate activity-log entries, and
  * the seed fixture must keep explicit primary keys.

Both are backend-independent, so they run identically on PostgreSQL.
"""

import io
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.common.models import ActivityLog
from apps.properties.models import Property

User = get_user_model()

FIXTURE_PATH = Path(settings.BASE_DIR) / "fixtures" / "seed_data.json"


class RawSignalGuardTests(TestCase):
    """`loaddata` must not generate activity logs for restored rows."""

    def test_loading_a_fixture_does_not_create_activity_logs(self):
        consultant = User.objects.create_user(
            username="fixture-agent", password="x", role="AGENT"
        )
        ActivityLog.objects.all().delete()

        # A normal save is expected to log.
        prop = Property.objects.create(
            title="ملک تست",
            internal_code="FIXTURE-1",
            consultant=consultant,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=1_000,
            area=80,
            address="آدرس",
            neighborhood="محله",
        )
        self.assertEqual(
            ActivityLog.objects.filter(target_type="property").count(),
            1,
            "a genuine create should be recorded in the activity feed",
        )

        # Serialise the real row so the fixture carries every field Django
        # expects (including the auto_now_add timestamps).
        buffer = io.StringIO()
        call_command(
            "dumpdata",
            "properties.Property",
            pks=str(prop.pk),
            indent=2,
            stdout=buffer,
        )
        serialised = buffer.getvalue()

        # The same row arriving through loaddata (raw=True) must stay silent.
        Property.objects.all().delete()
        ActivityLog.objects.all().delete()

        tmp = Path(settings.BASE_DIR) / "fixtures" / "_test_raw_guard.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(serialised, encoding="utf-8")
        try:
            call_command("loaddata", str(tmp), verbosity=0)
        finally:
            tmp.unlink(missing_ok=True)

        self.assertEqual(Property.objects.count(), 1, "the row should be restored")
        self.assertEqual(
            ActivityLog.objects.count(),
            0,
            "restoring a fixture must not invent activity-log entries",
        )


class SeedFixtureTests(TestCase):
    """The committed seed fixture must survive a round-trip unchanged."""

    def test_fixture_exists_and_is_valid_json(self):
        self.assertTrue(
            FIXTURE_PATH.exists(),
            f"seed fixture is missing: {FIXTURE_PATH}",
        )
        records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertGreater(len(records), 0, "the seed fixture should not be empty")

    def test_fixture_preserves_explicit_primary_keys(self):
        """IDs are referenced by the frontend, so they must not be renumbered.

        Dumping with ``--natural-primary`` drops the ``pk`` field and lets
        PostgreSQL reassign IDs on restore, which silently repoints properties
        at the wrong consultant.
        """
        records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        missing = [r["model"] for r in records if r.get("pk") is None]
        self.assertEqual(
            missing,
            [],
            "every record must carry an explicit pk — re-dump without --natural-primary",
        )

    def test_fixture_excludes_runtime_tables(self):
        """Content types and permissions are recreated by `migrate`."""
        records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        models = {r["model"] for r in records}
        for excluded in ("contenttypes.contenttype", "auth.permission", "sessions.session"):
            self.assertNotIn(
                excluded,
                models,
                f"{excluded} must be excluded — it collides on restore",
            )
