"""
Management command to clean up old in-app notifications.

Deletes read notifications older than --read-days (default 30) and
all notifications older than --all-days (default 90).

Usage:
    python manage.py cleanup_notifications
    python manage.py cleanup_notifications --read-days 14 --all-days 60
    python manage.py cleanup_notifications --dry-run
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import InAppNotification


class Command(BaseCommand):
    help = "Delete old in-app notifications to keep the table lean."

    def add_arguments(self, parser):
        parser.add_argument(
            "--read-days",
            type=int,
            default=30,
            help="Delete read notifications older than this many days (default: 30).",
        )
        parser.add_argument(
            "--all-days",
            type=int,
            default=90,
            help="Delete ALL notifications older than this many days (default: 90).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        read_days = options["read_days"]
        all_days = options["all_days"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no records will be deleted.\n"))

        # 1) Delete read notifications older than --read-days
        read_cutoff = now - timedelta(days=read_days)
        read_qs = InAppNotification.objects.filter(is_read=True, created_at__lt=read_cutoff)
        read_count = read_qs.count()

        if not dry_run and read_count:
            read_qs.delete()

        self.stdout.write(
            f"  Read notifications older than {read_days} days: "
            f"{'would delete' if dry_run else 'deleted'} {read_count} record(s)."
        )

        # 2) Delete ALL notifications older than --all-days
        all_cutoff = now - timedelta(days=all_days)
        all_qs = InAppNotification.objects.filter(created_at__lt=all_cutoff)
        all_count = all_qs.count()

        if not dry_run and all_count:
            all_qs.delete()

        self.stdout.write(
            f"  All notifications older than {all_days} days: "
            f"{'would delete' if dry_run else 'deleted'} {all_count} record(s)."
        )

        # Summary
        total = read_count + all_count
        remaining = InAppNotification.objects.count()
        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDry run complete. {total} record(s) would be removed."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nCleanup complete. {total} record(s) removed, {remaining} remaining."))
