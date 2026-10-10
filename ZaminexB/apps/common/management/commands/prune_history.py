from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from importlib import import_module

from apps.activity.models import ActivityLog

DEFAULT_RETENTION_DAYS = 180
DEFAULT_BATCH_SIZE = 5000


class Command(BaseCommand):
    help = (
        "Delete activity log entries older than --days and clear expired "
        "sessions. Both tables grow without bound otherwise."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help=(
                "Keep activity log entries for this many days "
                f"(default {DEFAULT_RETENTION_DAYS})."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=(
                "Rows per DELETE statement (default "
                f"{DEFAULT_BATCH_SIZE}). Larger is faster but holds its lock "
                "longer."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 0:
            raise CommandError("--days must not be negative")
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1")
        dry_run = options["dry_run"]

        cutoff = timezone.now() - timedelta(days=days)
        now = timezone.now()

        stale_logs = ActivityLog.objects.filter(created_at__lt=cutoff)
        log_count = stale_logs.count()
        expired_sessions = Session.objects.filter(expire_date__lt=now).count()

        verb = "Would delete" if dry_run else "Deleted"
        self.stdout.write(
            f"Activity log: {verb.lower()} {log_count} of "
            f"{ActivityLog.objects.count()} entries older than "
            f"{cutoff:%Y-%m-%d %H:%M}"
        )
        self.stdout.write(
            f"Sessions: {verb.lower()} {expired_sessions} of "
            f"{Session.objects.count()} expired rows"
        )

        if dry_run:
            return

        deleted_logs = 0
        while True:
            ids = list(
                ActivityLog.objects.filter(created_at__lt=cutoff).values_list(
                    "pk", flat=True
                )[:batch_size]
            )
            if not ids:
                break
            with transaction.atomic():
                removed, _ = ActivityLog.objects.filter(pk__in=ids).delete()
            deleted_logs += removed
            self.stdout.write(f"  ... {deleted_logs} activity entries so far")

        engine = import_module(settings.SESSION_ENGINE)
        engine.SessionStore.clear_expired()
        remaining = Session.objects.filter(expire_date__lt=timezone.now()).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Pruned {deleted_logs} activity entries and "
                f"{expired_sessions - remaining} expired sessions."
            )
        )
