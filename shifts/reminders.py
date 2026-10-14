"""Shift reminders: tell agents when check-in opens for their shift.

No Celery here (see docs/developer-guide/architecture.md): a daemon thread in
the web process checks once a minute, and the ``send_shift_reminders``
management command runs the same check for Task Scheduler or cron.
"""

import logging
import threading
import time as clock
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from shifts.models import ShiftAssignment
from shifts.services import check_in_opens_at, effective_interval

logger = logging.getLogger(__name__)

TICK_SECONDS = 60

_thread_started = False
_thread_lock = threading.Lock()


def send_due_reminders(now=None) -> int:
    """Remind every agent whose check-in window is open; returns how many were sent.

    A row is claimed by writing the start time it was reminded for, in one
    UPDATE, before anything is sent. A second process or a restart finds the
    row already claimed, and a moved start time no longer matches, so the
    agent is reminded again for the new time.
    """
    from accounts.models import User
    from notifications.services import notify_shift_reminder

    now = now or timezone.now()
    today = timezone.localdate(now)
    rows = (
        ShiftAssignment.objects.filter(
            date__in=[today - timedelta(days=1), today, today + timedelta(days=1)],
            user__status=User.Status.ACTIVE,
            user__user_type=User.UserType.SUPPORT,
            checked_in_at__isnull=True,
        )
        .select_related("user", "user__role", "shift_type", "shift_type__department")
    )
    sent = 0
    for row in rows:
        start_dt, _end_dt = effective_interval(row)
        if not (check_in_opens_at(row) <= now < start_dt):
            continue
        if row.reminded_for == start_dt:
            continue
        claimed = (
            ShiftAssignment.objects.filter(pk=row.pk)
            .exclude(reminded_for=start_dt)
            .update(reminded_for=start_dt)
        )
        if not claimed:
            continue
        try:
            notify_shift_reminder(row)
            sent += 1
        except Exception:  # noqa: BLE001 - one bad row must not stop the rest
            logger.exception("Shift reminder failed for assignment %s", row.pk)
    return sent


def _loop():
    while True:
        close_old_connections()
        try:
            send_due_reminders()
        except Exception:  # noqa: BLE001 - keep ticking after a DB hiccup
            logger.exception("Shift reminder tick failed")
        finally:
            close_old_connections()
        clock.sleep(TICK_SECONDS)


def ensure_reminder_thread(**_kwargs):
    """Start the once-a-minute reminder thread (first request only).

    Tests run with EMAIL_QUEUE_SYNC and never start it; they call
    send_due_reminders() directly.
    """
    global _thread_started
    if getattr(settings, "EMAIL_QUEUE_SYNC", False):
        return
    with _thread_lock:
        if _thread_started:
            return
        threading.Thread(target=_loop, name="shift-reminders", daemon=True).start()
        _thread_started = True
