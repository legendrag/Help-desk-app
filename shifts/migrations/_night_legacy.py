"""The old night-window rules, frozen for migrations 0004 and 0005 only.

Night used to be worked out from a department night window (default 6 PM to
6 AM). Shift types are now marked night by hand (migration 0008). The leading
underscore keeps Django's migration loader from reading this as a migration.
"""

from datetime import date, time, timedelta

from django.utils import timezone

from shifts.services import aware_on, interval_for


def _night_segments(day, night_starts_at, night_ends_at):
    starts = time(night_starts_at.hour, night_starts_at.minute)
    ends = time(night_ends_at.hour, night_ends_at.minute)
    if starts == ends:
        return []
    if ends < starts:
        return [
            (aware_on(day, time(0, 0)), aware_on(day, ends)),
            (aware_on(day, starts), aware_on(day + timedelta(days=1), time(0, 0))),
        ]
    return [(aware_on(day, starts), aware_on(day, ends))]


def split_day_night_minutes(start_dt, end_dt, night_starts_at, night_ends_at=time(6, 0)):
    if end_dt <= start_dt:
        return 0, 0
    tz = timezone.get_current_timezone()
    first = timezone.localtime(start_dt, tz).date()
    last = timezone.localtime(end_dt - timedelta(microseconds=1), tz).date()
    total = int((end_dt - start_dt).total_seconds() // 60)
    night_m = 0
    cursor = first
    while cursor <= last:
        for seg_start, seg_end in _night_segments(cursor, night_starts_at, night_ends_at):
            clip_start = max(start_dt, seg_start)
            clip_end = min(end_dt, seg_end)
            if clip_end > clip_start:
                night_m += int((clip_end - clip_start).total_seconds() // 60)
        cursor += timedelta(days=1)
    return total - night_m, night_m


def is_night_shift(start_t, end_t, night_starts_at, night_ends_at, mode="auto") -> bool:
    """More than half the hours in the night window, unless set Always or Never."""
    if mode == "always":
        return True
    if mode == "never":
        return False
    start_dt, end_dt = interval_for(date(2026, 1, 5), start_t, end_t)
    day_m, night_m = split_day_night_minutes(start_dt, end_dt, night_starts_at, night_ends_at)
    return night_m * 2 > day_m + night_m


def type_includes_night(start_t, end_t, night_starts_at) -> bool:
    """The first rule: any minute after the night start."""
    start_dt, end_dt = interval_for(date(2026, 1, 5), start_t, end_t)
    _day_m, night_m = split_day_night_minutes(start_dt, end_dt, night_starts_at, time(0, 0))
    return night_m > 0
