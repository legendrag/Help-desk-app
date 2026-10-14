"""Who is on shift: the rules behind Available now, the chat popup and Transfer.

One place decides a shift's state so every screen agrees with the timeline.
"""

from datetime import datetime, time, timedelta

from django.utils import timezone

from shifts.access import can_check_in
from shifts.models import ShiftAssignment
from shifts.services import (
    CHECKED_IN,
    COMPLETED,
    MISSED,
    NOT_CHECKED_IN,
    ON_SHIFT,
    effective_interval,
    effective_times,
    settle_check_in,
    shift_outcome,
)

# Bar states on the Available now timeline, from shifts.services.shift_outcome.
TIMELINE_STATES = {
    CHECKED_IN: "on",
    ON_SHIFT: "on",
    NOT_CHECKED_IN: "late",
    COMPLETED: "done",
    MISSED: "missed",
}
# The help desk day: 9 AM to 6 AM next morning. Nobody works 6 to 9 AM,
# so the timeline leaves that stretch out.
TIMELINE_START = time(9, 0)
TIMELINE_END = time(6, 0)


def _window_start_time(day):
    """9 AM, or the hour of the earliest shift that day starting between 6 and 9 AM.

    Shifts starting before 6 AM belong to the night before (the previous
    window), so only 6 to 9 AM starts pull the window earlier.
    """
    rows = ShiftAssignment.objects.filter(date=day).select_related("shift_type").only(
        "start_time_override", "end_time_override", "shift_type__start_time", "shift_type__end_time",
    )
    early = [
        effective_times(row)[0]
        for row in rows
        if TIMELINE_END <= effective_times(row)[0] < TIMELINE_START
    ]
    if not early:
        return TIMELINE_START
    return time(min(early).hour, 0)


def timeline_window(now):
    """The window holding ``now``: 9 AM (earlier if a shift starts sooner) to 6 AM.

    From 6 AM until the window opens, it is the one about to start.
    """
    local = timezone.localtime(now)
    day = local.date()
    if local.time() < TIMELINE_END:
        day -= timedelta(days=1)
    # Not aware_on(): a DST jump must not make the board fail to load.
    start = timezone.make_aware(datetime.combine(day, _window_start_time(day)))
    end = timezone.make_aware(datetime.combine(day + timedelta(days=1), TIMELINE_END))
    return day, start, end


def timeline_rows(now, day, window_start, window_end, department_id=None):
    """Shifts overlapping the window as ``(row, start_dt, end_dt, state)``.

    State is on, late, later, done or missed. Check-ins are settled in memory
    only, and an early check-in stays "later" until the shift starts.
    """
    query = ShiftAssignment.objects.filter(
        date__in=[day - timedelta(days=1), day, day + timedelta(days=1)],
    ).select_related("user", "user__role", "shift_type", "shift_type__department")
    if department_id is not None:
        query = query.filter(shift_type__department_id=department_id)
    uses_check_in = {}
    rows = []
    for row in query:
        settle_check_in(row, now, save=False)
        start_dt, end_dt = effective_interval(row)
        if end_dt <= window_start or start_dt >= window_end:
            continue
        if row.user_id not in uses_check_in:
            uses_check_in[row.user_id] = can_check_in(row.user)
        outcome = shift_outcome(row, now, uses_check_in[row.user_id])
        state = "later" if now < start_dt else TIMELINE_STATES.get(outcome, "later")
        rows.append((row, start_dt, end_dt, state))
    return rows


def on_shift_now(department_id=None, now=None):
    """``{user_id: shift end}`` for everyone on shift right now."""
    now = now or timezone.now()
    day, window_start, window_end = timeline_window(now)
    ends = {}
    for row, _start_dt, end_dt, state in timeline_rows(now, day, window_start, window_end, department_id):
        if state == "on":
            ends[row.user_id] = max(end_dt, ends.get(row.user_id, end_dt))
    return ends
