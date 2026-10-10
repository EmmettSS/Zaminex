from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, models, transaction
from django.db.models import Max
from django.test import TestCase
from django.utils import timezone

from apps.common.management.commands import resync_sequences
from apps.common.management.commands.resync_sequences import (
    next_id_for,
    sequence_columns,
)
from apps.notifications.models import Notification
from apps.properties.models import Property
from apps.tasks.models import Task

User = get_user_model()


def run_command(*args, **kwargs):
    out, err = StringIO(), StringIO()
    try:
        call_command("resync_sequences", *args, stdout=out, stderr=err, **kwargs)
        status = 0
    except SystemExit as exc:
        status = exc.code if exc.code is not None else 0
    return out.getvalue() + err.getvalue(), status


def sequence_of(table, column="id"):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT n.nspname, s.relname FROM pg_class s "
            "JOIN pg_namespace n ON n.oid = s.relnamespace "
            "WHERE s.oid = pg_get_serial_sequence(%s, %s)::regclass",
            [f'"{table}"', column],
        )
        return cursor.fetchone()


def sequence_state(table, column="id"):
    schema, name = sequence_of(table, column)
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT last_value, is_called FROM "{schema}"."{name}"')
        return cursor.fetchone()


def force_sequence(table, value, column="id"):
    schema, name = sequence_of(table, column)
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT setval('\"{schema}\".\"{name}\"'::regclass, %s, true)", [value]
        )


def highest_id(model):
    return model.objects.aggregate(highest=Max("id"))["highest"]


class NextIdHelperTests(TestCase):
    def test_called_sequence_hands_out_the_next_value(self):
        self.assertEqual(next_id_for(5, True), 6)

    def test_untouched_sequence_hands_out_its_own_value(self):
        self.assertEqual(next_id_for(5, False), 5)


class SequenceColumnsTests(TestCase):
    def test_finds_django_auto_increment_primary_keys(self):
        found = {(table, column) for table, column, _, _ in sequence_columns()}

        self.assertIn(("properties_property", "id"), found)
        self.assertIn(("common_notification", "id"), found)
        self.assertIn(("django_migrations", "id"), found)

    def test_every_row_points_at_a_real_sequence(self):
        for _, _, schema, name in sequence_columns():
            self.assertTrue(schema)
            self.assertTrue(name.endswith("_id_seq"))

    def test_matches_djangos_own_view_of_auto_primary_keys(self):
        found = {table for table, *_ in sequence_columns()}
        auto_fields = (
            models.AutoField,
            models.BigAutoField,
            models.SmallAutoField,
        )

        for model in apps.get_models():
            with self.subTest(model=model._meta.label):
                if isinstance(model._meta.pk, auto_fields):
                    self.assertIn(model._meta.db_table, found)
                else:
                    self.assertNotIn(model._meta.db_table, found)


class ResyncSequencesCommandTests(TestCase):
    def setUp(self):
        self.consultant = User.objects.create_user(
            username="resync-agent", password="x", role="AGENT"
        )

    def make_property(self, title="ملک تست"):
        return Property.objects.create(
            title=title,
            consultant=self.consultant,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            area=80,
            address="آدرس تست",
        )

    def make_task(self, title="وظیفه تست"):
        return Task.objects.create(
            title=title,
            created_by=self.consultant,
            assigned_to=self.consultant,
            due_date=timezone.now().date(),
        )

    def test_a_healthy_database_reports_nothing_to_do(self):
        self.make_property()

        output, status = run_command()

        self.assertEqual(status, 0)
        self.assertNotIn("BEHIND", output)
        self.assertNotIn("FIXED", output)
        self.assertIn("هماهنگ است", output)

    def test_dry_run_reports_the_problem_and_exits_with_1(self):
        self.make_property()
        force_sequence("properties_property", 1)

        output, status = run_command("--dry-run")

        self.assertEqual(status, 1)
        self.assertIn("properties_property", output)
        self.assertIn("BEHIND", output)
        self.assertNotIn("FIXED", output)

    def test_dry_run_changes_nothing(self):
        self.make_property()
        force_sequence("properties_property", 1)
        before = sequence_state("properties_property")

        run_command("--dry-run")

        self.assertEqual(sequence_state("properties_property"), before)

    def test_fix_moves_the_sequence_and_the_next_row_stops_colliding(self):
        self.make_property()
        highest = highest_id(Property)
        force_sequence("properties_property", 1)

        output, status = run_command()

        self.assertEqual(status, 0)
        self.assertIn("FIXED", output)
        self.assertEqual(sequence_state("properties_property"), (highest, True))

        created = self.make_property("ملک بعدی")
        self.assertEqual(created.id, highest + 1)

    def test_fix_is_idempotent(self):
        self.make_property()
        force_sequence("properties_property", 1)

        first, _ = run_command()
        after_first = sequence_state("properties_property")
        second, status = run_command()

        self.assertIn("FIXED", first)
        self.assertEqual(status, 0)
        self.assertNotIn("FIXED", second)
        self.assertEqual(sequence_state("properties_property"), after_first)

    def test_a_sequence_that_is_ahead_is_never_moved_backwards(self):
        for index in range(3):
            self.make_property(f"ملک {index}")
        newest = Property.objects.order_by("-id")[:2]
        Property.objects.filter(id__in=[p.id for p in newest]).delete()
        before = sequence_state("properties_property")
        highest = highest_id(Property)
        self.assertGreater(before[0], highest)

        output, status = run_command()

        self.assertEqual(status, 0)
        self.assertNotIn("FIXED", output)
        self.assertEqual(sequence_state("properties_property"), before)

        created = self.make_property("ملک پس از حذف")
        self.assertEqual(created.id, before[0] + 1)

    def test_the_boundary_case_counts_as_a_collision(self):
        self.make_property()
        highest = highest_id(Property)
        force_sequence("properties_property", highest - 1)
        self.assertEqual(next_id_for(*sequence_state("properties_property")), highest)

        output, _ = run_command()

        self.assertIn("FIXED", output)
        self.assertEqual(sequence_state("properties_property"), (highest, True))

    def test_one_id_above_the_max_is_healthy(self):
        self.make_property()
        highest = highest_id(Property)
        force_sequence("properties_property", highest)

        output, status = run_command()

        self.assertEqual(status, 0)
        self.assertNotIn("FIXED", output)
        self.assertEqual(self.make_property("ملک مرزی").id, highest + 1)

    def test_table_filter_touches_only_the_named_table(self):
        self.make_property()
        self.make_task()
        force_sequence("properties_property", 1)
        force_sequence("tasks_task", 1)
        task_sequence_before = sequence_state("tasks_task")

        output, status = run_command("--table", "properties_property")

        self.assertEqual(status, 0)
        self.assertIn("properties_property", output)
        self.assertIn("FIXED", output)
        self.assertNotIn("tasks_task", output)
        self.assertEqual(sequence_state("tasks_task"), task_sequence_before)

    def test_table_filter_can_repair_the_second_table(self):
        self.make_task()
        highest = highest_id(Task)
        force_sequence("tasks_task", 1)

        _, status = run_command("--table", "tasks_task")

        self.assertEqual(status, 0)
        self.assertEqual(sequence_state("tasks_task"), (highest, True))

    def test_unknown_table_is_rejected_with_a_suggestion(self):
        with self.assertRaises(CommandError) as caught:
            call_command("resync_sequences", "--table", "properties_propert")

        self.assertIn("properties_property", str(caught.exception))

    def test_quoted_table_names_are_handled(self):
        table = "resync probe table"
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table}" '
                "(id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, note text)"
            )
            cursor.execute(
                f'INSERT INTO "{table}" (note) VALUES (%s), (%s), (%s)',
                ["a", "b", "c"],
            )
        force_sequence(table, 1)

        output, status = run_command("--table", table)

        self.assertEqual(status, 0)
        self.assertIn("FIXED", output)
        self.assertEqual(sequence_state(table), (3, True))

        with connection.cursor() as cursor:
            cursor.execute(f'INSERT INTO "{table}" (note) VALUES (%s)', ["d"])
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT max(id) FROM "{table}"')
            self.assertEqual(cursor.fetchone()[0], 4)

    def test_an_empty_table_keeps_its_first_id(self):
        table = "resync empty table"
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table}" '
                "(id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, note text)"
            )

        output, status = run_command("--table", table)

        self.assertEqual(status, 0)
        self.assertNotIn("FIXED", output)
        self.assertEqual(sequence_state(table), (1, False))

        with connection.cursor() as cursor:
            cursor.execute(f'INSERT INTO "{table}" (note) VALUES (%s)', ["first"])
            cursor.execute(f'SELECT id FROM "{table}"')
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_verbose_run_lists_healthy_tables(self):
        output, status = run_command(verbosity=2)

        self.assertEqual(status, 0)
        self.assertIn("properties_property", output)
        self.assertIn("tickets_ticket", output)

    def test_a_missing_schema_is_rejected(self):
        with self.assertRaises(CommandError) as caught:
            call_command("resync_sequences", "--schema", "no_such_schema")

        self.assertIn("does not exist", str(caught.exception))

    def test_a_schema_without_tables_points_to_migrate(self):
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA resync_empty_schema")

        with self.assertRaises(CommandError) as caught:
            call_command("resync_sequences", "--schema", "resync_empty_schema")

        self.assertIn("migrate", str(caught.exception))

    def test_a_non_postgres_connection_is_rejected(self):
        with patch.object(
            resync_sequences, "connection", SimpleNamespace(vendor="sqlite")
        ):
            with self.assertRaises(CommandError) as caught:
                call_command("resync_sequences")

        self.assertIn("PostgreSQL", str(caught.exception))


class ReportedRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="resync-notify", password="x", role="AGENT"
        )

    def test_notifications_collide_until_the_sequence_is_repaired(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT setval('common_notification_id_seq', 13, true)")
        Notification.objects.all().delete()
        for index in range(20):
            Notification.objects.create(
                user=self.user,
                type="ticket_created",
                title=f"اعلان {index}",
                message="پیام",
                metadata={"ticketId": index},
            )
        highest = highest_id(Notification)
        force_sequence("common_notification", 13)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Notification.objects.create(
                    user=self.user,
                    type="ticket_created",
                    title="باید شکست بخورد",
                    message="پیام",
                    metadata={"ticketId": 99},
                )

        output, status = run_command()

        self.assertEqual(status, 0)
        self.assertIn("common_notification", output)
        self.assertIn("FIXED", output)
        self.assertEqual(sequence_state("common_notification"), (highest, True))

        repaired = Notification.objects.create(
            user=self.user,
            type="ticket_created",
            title="بعد از اصلاح",
            message="پیام",
            metadata={"ticketId": 100},
        )
        self.assertEqual(repaired.id, highest + 1)
