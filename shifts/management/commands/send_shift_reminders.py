"""
Send shift reminders whose check-in window is open.

The web process already does this once a minute. Schedule this command
(Task Scheduler / cron, every few minutes) when the site runs more than one
process or is often idle. Reminders are claimed in the database, so running
both never sends one twice.

Usage:
    python manage.py send_shift_reminders
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from shifts.reminders import send_due_reminders


class Command(BaseCommand):
    help = "Send shift reminders for shifts whose check-in window is open."

    def handle(self, *args, **options):
        # Mail and web push normally go to a daemon thread that would die
        # with this process; run them inline instead.
        settings.EMAIL_QUEUE_SYNC = True
        sent = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} shift reminder(s)."))
