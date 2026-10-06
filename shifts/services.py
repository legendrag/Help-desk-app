from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.utils import timezone
from django.utils.translation import gettext as _

from shifts.access import is_shift_manager

WORKER_HOURS_LOOKBACK_DAYS = 7
WORKER_HOURS_MAX_MINUTES = 16 * 60
CHECK_IN_EARLY_MINUTES = 30
NIGHT_ROTATION_LOOKBACK_DAYS = 14
REPEAT_WEEKS_MAX = 12


def saturday_of(day: date) -> date:
    return day - timedelta(days=(day.weekday() - 5) % 7)


def normalize_start(day: date, view: str) -> date:
    if view == "month":
        return day.replace(day=1)
    return saturday_of(day)


def week_dates(saturday: date) -> list[date]:
    return [saturday + timedelta(days=offset) for offset in range(7)]


def month_dates(first: date) -> list[date]:
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1, day=1)
    else:
        nxt = first.replace(month=first.month + 1, day=1)
    days = (nxt - first).days
    return [first + timedelta(days=offset) for offset in range(days)]


def effective_times(assignment):
    if assignment.start_time_override is not None and assignment.end_time_override is not None:
        return assignment.start_time_override, assignment.end_time_override
    return assignment.shift_type.start_time, assignment.shift_type.end_time


def effective_crosses_midnight(start_t: time, end_t: time) -> bool:
    return end_t < start_t


def aware_on(on: date, clock: time):
    tz = timezone.get_current_timezone()
    naive = datetime.combine(on, clock)
    # Django 6 make_aware() uses replace(tzinfo=...) and does not raise
    # NonExistentTimeError (that name is not in django.utils.timezone).
    aware = timezone.make_aware(naive, tz)
    if aware.astimezone(dt_timezone.utc).astimezone(tz).replace(tzinfo=None) != naive:
        raise ValueError(_("That time does not exist on this date."))
    return aware


def interval_for(on: date, start_t: time, end_t: time):
    start_dt = aware_on(on, start_t)
    end_day = on + timedelta(days=1) if effective_crosses_midnight(start_t, end_t) else on
    end_dt = aware_on(end_day, end_t)
    return start_dt, end_dt


def effective_interval(assignment):
    start_t, end_t = effective_times(assignment)
    return interval_for(assignment.date, start_t, end_t)


def overlaps(left, right) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def clock_length(start_t: time, end_t: time):
    if start_t == end_t:
        return 0, 0
    anchor = date(2026, 1, 5)
    start_dt, end_dt = interval_for(anchor, start_t, end_t)
    total = int((end_dt - start_dt).total_seconds() // 60)
    if effective_crosses_midnight(start_t, end_t):
        after = end_t.hour * 60 + end_t.minute
    else:
        after = 0
    return total, after


def clipped_day_night_minutes(assignment, range_start, range_end):
    start_dt, end_dt = effective_interval(assignment)
    clip_start = max(start_dt, range_start)
    clip_end = min(end_dt, range_end)
    if clip_end <= clip_start:
        return 0, 0
    minutes = int((clip_end - clip_start).total_seconds() // 60)
    if assignment.shift_type.is_night:
        return 0, minutes
    return minutes, 0


def overrides_set_by_worker(assignment) -> bool:
    if assignment.start_time_override is None or assignment.end_time_override is None:
        return False
    setter = assignment.times_set_by
    if setter is None:
        return False
    return not is_shift_manager(setter)


def check_in_marker(assignment, now) -> str:
    if assignment.shift_type.is_night:
        return ""
    today = timezone.localdate()
    if assignment.date > today:
        return ""
    if assignment.checked_in_at and assignment.date <= today:
        return "checked"
    if assignment.date < today:
        return "missed"
    start_dt, _end = effective_interval(assignment)
    if now >= start_dt:
        return "not"
    return ""


def check_in_state(assignment, now) -> str:
    start_dt, end_dt = effective_interval(assignment)
    opens = start_dt - timedelta(minutes=CHECK_IN_EARLY_MINUTES)
    if now < opens:
        return "early"
    if now >= end_dt:
        return "closed"
    return "open"


def neighbor_conflict(assignment, start_dt, end_dt, exclude_pk=None):
    from shifts.models import ShiftAssignment

    qs = ShiftAssignment.objects.filter(
        user_id=assignment.user_id,
        date__gte=assignment.date - timedelta(days=1),
        date__lte=assignment.date + timedelta(days=1),
    ).select_related("shift_type", "user")
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    proposed = (start_dt, end_dt)
    for other in qs:
        if overlaps(proposed, effective_interval(other)):
            return other
    return None


def plan_copy(source_rows, day_shift, acting_user):
    planned = []
    for source in source_rows:
        item = {
            "user_id": source.user_id,
            "date": source.date + day_shift,
            "shift_type_id": source.shift_type_id,
            "start": None,
            "end": None,
            "times_set_by_id": None,
            "times_set_at": None,
            "skip": None,
        }
        if source.shift_type.archived:
            item["skip"] = "archived shift type"
        elif (
            not overrides_set_by_worker(source)
            and source.start_time_override is not None
            and source.end_time_override is not None
        ):
            item["start"] = source.start_time_override
            item["end"] = source.end_time_override
            item["times_set_by_id"] = acting_user.pk
            item["times_set_at"] = timezone.now()
        planned.append(item)
    return planned


def overlap_message(other) -> str:
    start_t, end_t = effective_times(other)
    return _("This shift overlaps %(name)s on %(date)s (%(start)s–%(end)s).") % {
        "name": other.shift_type.name,
        "date": other.date.isoformat(),
        "start": start_t.strftime("%H:%M"),
        "end": end_t.strftime("%H:%M"),
    }


def suggest_nights(people, dates, shift_type, existing_by_user):
    if not dates:
        return []
    start = dates[0]
    lookback_from = start - timedelta(days=NIGHT_ROTATION_LOOKBACK_DAYS)
    stats = {}
    for person in people:
        rows = existing_by_user.get(person.pk, [])
        nights = [
            row.date for row in rows
            if lookback_from <= row.date < start and row.shift_type.is_night
        ]
        stats[person.pk] = {
            "lookback": len(nights),
            "last": max(nights) if nights else None,
            "proposed": 0,
            "dates": {row.date for row in rows},
            "night_dates": {row.date for row in rows if row.shift_type.is_night},
            "intervals": [effective_interval(row) for row in rows],
        }
    result = []
    for day in dates:
        target = interval_for(day, shift_type.start_time, shift_type.end_time)
        preferred = []
        backup = []
        for person in people:
            st = stats[person.pk]
            if day in st["dates"]:
                continue
            if any(overlaps(target, existing) for existing in st["intervals"]):
                continue
            if (day - timedelta(days=1)) in st["night_dates"]:
                backup.append(person)
            else:
                preferred.append(person)
        pool = preferred or backup
        if not pool:
            result.append({"date": day, "gap": True})
            continue

        def sort_key(person, stats=stats):
            st = stats[person.pk]
            last = st["last"] or date.min
            return (st["lookback"] + st["proposed"], last, person.pk)

        chosen = min(pool, key=sort_key)
        st = stats[chosen.pk]
        st["proposed"] += 1
        st["dates"].add(day)
        st["night_dates"].add(day)
        st["intervals"].append(target)
        result.append({
            "date": day,
            "user_id": chosen.pk,
            "back_to_back": not preferred,
        })
    return result
