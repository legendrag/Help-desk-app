import hashlib
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.utils import timezone
from django.utils.translation import gettext as _

from shifts.clock import format_clock

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


DEFAULT_NIGHT_STARTS = time(18, 0)
DEFAULT_NIGHT_ENDS = time(6, 0)


def night_window_for(department):
    """(night starts, night ends) for a department, cached on the instance."""
    cached = getattr(department, "_night_window", None)
    if cached is not None:
        return cached
    from shifts.models import DepartmentShiftSettings

    try:
        settings = department.shift_settings
        starts, ends = settings.night_starts_at, settings.night_ends_at
    except DepartmentShiftSettings.DoesNotExist:
        starts, ends = DEFAULT_NIGHT_STARTS, DEFAULT_NIGHT_ENDS
    department._night_window = (time(starts.hour, starts.minute), time(ends.hour, ends.minute))
    return department._night_window


def _night_segments(day, night_starts_at, night_ends_at):
    """The night stretches that fall on one calendar day."""
    starts = time(night_starts_at.hour, night_starts_at.minute)
    ends = time(night_ends_at.hour, night_ends_at.minute)
    if starts == ends:
        return []
    if ends < starts:
        # The usual case, e.g. 6 PM to 6 AM: early morning plus late evening.
        return [
            (aware_on(day, time(0, 0)), aware_on(day, ends)),
            (aware_on(day, starts), aware_on(day + timedelta(days=1), time(0, 0))),
        ]
    return [(aware_on(day, starts), aware_on(day, ends))]


def split_day_night_minutes(start_dt, end_dt, night_starts_at, night_ends_at=DEFAULT_NIGHT_ENDS):
    """Split an interval into day minutes and night minutes.

    Night runs from the department's night start to its night end, across
    midnight (by default 6 PM to 6 AM). Everything else is day.
    """
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
    """Whether a shift type counts as a night shift.

    Automatic: more than half of its hours are night hours. A manager can
    override that with Always or Never; night hours are counted either way.
    """
    if mode == "always":
        return True
    if mode == "never":
        return False
    anchor = date(2026, 1, 5)
    start_dt, end_dt = interval_for(anchor, start_t, end_t)
    day_m, night_m = split_day_night_minutes(start_dt, end_dt, night_starts_at, night_ends_at)
    return night_m * 2 > day_m + night_m


def type_includes_night(start_t, end_t, night_starts_at) -> bool:
    """Old rule (any minute after the night start). Kept for migration 0004 only."""
    anchor = date(2026, 1, 5)
    start_dt, end_dt = interval_for(anchor, start_t, end_t)
    _day_m, night_m = split_day_night_minutes(start_dt, end_dt, night_starts_at, time(0, 0))
    return night_m > 0


def clipped_day_night_minutes(assignment, range_start, range_end):
    start_dt, end_dt = effective_interval(assignment)
    clip_start = max(start_dt, range_start)
    clip_end = min(end_dt, range_end)
    if clip_end <= clip_start:
        return 0, 0
    starts, ends = night_window_for(assignment.shift_type.department)
    return split_day_night_minutes(clip_start, clip_end, starts, ends)


def overrides_set_by_worker(assignment) -> bool:
    if assignment.start_time_override is None or assignment.end_time_override is None:
        return False
    setter = assignment.times_set_by
    if setter is None:
        return False
    return not is_shift_manager(setter)


def settle_check_in(assignment, now, save=True) -> bool:
    """Clear a check-in once its effective end has passed.

    ``checked_out_at`` stays set so a later edit of the end time cannot
    look like a shift that was never checked in. With ``save=False`` only
    the in-memory row changes, for read-only endpoints.
    """
    if assignment is None or not getattr(assignment, "pk", None):
        return False
    if not assignment.checked_in_at:
        return False
    _start_dt, end_dt = effective_interval(assignment)
    if now < end_dt:
        return False
    assignment.checked_in_at = None
    assignment.checked_out_at = end_dt
    if save:
        assignment.save(update_fields=["checked_in_at", "checked_out_at", "updated_at"])
    return True


# Where a shift stands. The rota, My shifts and the work-hours report all read
# this, so one shift never shows two different outcomes on two pages.
UPCOMING = "upcoming"
CHECKED_IN = "checked_in"
ON_SHIFT = "on_shift"              # running, for someone who does not check in
NOT_CHECKED_IN = "not_checked_in"  # running, check-in user, not checked in
COMPLETED = "completed"
MISSED = "missed"


def shift_outcome(assignment, now, uses_check_in) -> str:
    """One status per shift. Call after ``settle_check_in`` (``save=False`` is fine).

    An ended shift is Completed when the person was present (auto check-out
    stamps the shift end; a manager clearing the check-in stamps an earlier
    time and does not count), or when they are not on check-in at all.
    """
    start_dt, end_dt = effective_interval(assignment)
    if now >= end_dt:
        present = bool(assignment.checked_in_at) or bool(
            assignment.checked_out_at and assignment.checked_out_at >= end_dt
        )
        if present or not uses_check_in:
            return COMPLETED
        return MISSED
    if assignment.checked_in_at:
        return CHECKED_IN
    if now < start_dt:
        return UPCOMING
    return NOT_CHECKED_IN if uses_check_in else ON_SHIFT


def check_in_marker(assignment, now, uses_check_in) -> str:
    """Rota cell status: '', 'checked', 'not', 'completed' or 'missed'."""
    return {
        CHECKED_IN: "checked",
        NOT_CHECKED_IN: "not",
        COMPLETED: "completed",
        MISSED: "missed",
    }.get(shift_outcome(assignment, now, uses_check_in), "")


def check_in_opens_at(assignment) -> datetime:
    start_dt, _ = effective_interval(assignment)
    return start_dt - timedelta(minutes=CHECK_IN_EARLY_MINUTES)


def check_in_state(assignment, now) -> str:
    _start_dt, end_dt = effective_interval(assignment)
    opens = check_in_opens_at(assignment)
    if now < opens:
        return "early"
    if now >= end_dt:
        return "closed"
    return "open"


def check_in_visible(assignment, now) -> bool:
    if assignment is None:
        return False
    _start_dt, end_dt = effective_interval(assignment)
    if now >= end_dt:
        return False
    opens = check_in_opens_at(assignment)
    return now >= opens


def next_check_in_change(assignments, now) -> int | None:
    transitions = []
    for a in assignments:
        opens = check_in_opens_at(a)
        _start_dt, end_dt = effective_interval(a)
        if opens > now:
            transitions.append(opens)
        if end_dt > now:
            transitions.append(end_dt)
    if not transitions:
        return None
    earliest = min(transitions)
    diff = int((earliest - now).total_seconds()) + 2
    return max(5, min(diff, 86400))


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
        "start": format_clock(start_t),
        "end": format_clock(end_t),
    }


# Bulk assign (Calculator) and the rota's night auto-fill share this planner.
BULK_MAX_DAYS = 92
# Friday and Saturday, as on the rota (date.weekday()).
WEEKEND_DAYS = (4, 5)


def is_weekend(day):
    return day.weekday() in WEEKEND_DAYS


def _same_kind(row, shift_type):
    """Rows that count toward a person's share of ``shift_type``: any night
    for a night type (nights are what people trade), else that exact type."""
    if shift_type.is_night:
        return row.shift_type.is_night
    return row.shift_type_id == shift_type.pk


def _shift_minutes(shift_type):
    return clock_length(shift_type.start_time, shift_type.end_time)[0]


def plan_bulk(people, dates, shift_type, existing_by_user, *, per_day=1, everyone=False, covered=None):
    """Plan ``shift_type`` for ``people`` on ``dates`` (skipped days already removed).

    ``everyone``: each person gets the shift on every date they are free.

    Otherwise ``per_day`` people a day, split evenly across this run:

    * a day that already has ``covered[day]`` people on this shift needs fewer,
      and the shifts people already hold on these dates count toward their share;
    * fewest shifts in this run first, then (on a weekend day) fewest weekend
      shifts, then fewest in the lookback before the run, then longest since
      the last one, then a per-run rotation so ties don't always go to the
      same person;
    * weekend days are planned first, so they are shared out evenly too;
    * a night type avoids nights in a row (the night before or after) unless
      that would make the split uneven.

    Nobody is given a shift that overlaps one they already have, or the same
    shift twice on one day. Returns ``(plan, gaps)``: plan items are
    ``{"date", "user_id", "back_to_back"}``; gaps are ``{"date", "missing"}``.
    """
    plan, gaps = [], []
    if not dates or not people:
        return plan, gaps
    covered = covered or {}
    run_dates = set(dates)
    first = min(dates)
    lookback_from = first - timedelta(days=NIGHT_ROTATION_LOOKBACK_DAYS)
    salt = first.toordinal()
    stats = {}
    for person in people:
        rows = existing_by_user.get(person.pk, [])
        kind = [row for row in rows if _same_kind(row, shift_type)]
        in_run = [row for row in kind if row.date in run_dates and row.shift_type_id == shift_type.pk]
        before = [row.date for row in kind if lookback_from <= row.date < first]
        stats[person.pk] = {
            "run": len(in_run),
            "weekend": sum(1 for row in in_run if is_weekend(row.date)),
            "lookback": len(before),
            "last": max(before) if before else None,
            "has_type": {row.date for row in rows if row.shift_type_id == shift_type.pk},
            "night_dates": {row.date for row in rows if row.shift_type.is_night},
            "intervals": [effective_interval(row) for row in rows],
            # A tie order that changes with every run (hash of person and start).
            "spin": hashlib.sha1(f"{person.pk}:{salt}".encode()).digest()[:4],
        }

    def free(person, day, target):
        st = stats[person.pk]
        if day in st["has_type"]:
            return False
        return not any(overlaps(target, existing) for existing in st["intervals"])

    def take(person, day, target, back_to_back):
        st = stats[person.pk]
        st["run"] += 1
        if is_weekend(day):
            st["weekend"] += 1
        st["last"] = day
        st["has_type"].add(day)
        if shift_type.is_night:
            st["night_dates"].add(day)
        st["intervals"].append(target)
        plan.append({"date": day, "user_id": person.pk, "back_to_back": back_to_back})

    # Weekend days first, so they are shared out evenly before the weekdays
    # even up the totals (otherwise the weekend count only broke ties).
    for day in sorted(dates, key=lambda day: (not is_weekend(day), day)):
        target = interval_for(day, shift_type.start_time, shift_type.end_time)
        if everyone:
            for person in people:
                if free(person, day, target):
                    take(person, day, target, False)
            continue
        need = per_day - covered.get(day, 0)
        weekend = is_weekend(day)

        def key(person):
            st = stats[person.pk]
            return (
                st["run"],
                st["weekend"] if weekend else 0,
                st["lookback"],
                st["last"] or date.min,
                st["spin"],
            )

        for slot in range(max(need, 0)):
            pool = [person for person in people if free(person, day, target)]
            if not pool:
                gaps.append({"date": day, "missing": need - slot})
                break
            chosen = min(pool, key=key)
            back_to_back = False
            if shift_type.is_night:
                rested = [
                    person for person in pool
                    if not ({day - timedelta(days=1), day + timedelta(days=1)} & stats[person.pk]["night_dates"])
                ]
                # Prefer someone off the night before and after, but only among
                # those with the fewest shifts: the split stays even.
                if rested and stats[min(rested, key=key).pk]["run"] == stats[chosen.pk]["run"]:
                    chosen = min(rested, key=key)
                else:
                    back_to_back = True
            take(chosen, day, target, back_to_back)
    plan.sort(key=lambda item: item["date"])
    gaps.sort(key=lambda gap: gap["date"])
    return plan, gaps


def suggest_nights(people, dates, shift_type, existing_by_user):
    """One person a night (the rota's auto-fill), with a reason on back-to-back nights."""
    plan, gaps = plan_bulk(people, dates, shift_type, existing_by_user)
    by_date = {item["date"]: item for item in plan}
    gap_dates = {gap["date"] for gap in gaps}
    result = []
    for day in dates:
        if day in gap_dates or day not in by_date:
            result.append({"date": day, "gap": True})
            continue
        item = dict(by_date[day], reason="")
        if item["back_to_back"]:
            others_assigned = any(
                row.date == day
                for person in people if person.pk != item["user_id"]
                for row in existing_by_user.get(person.pk, [])
            )
            if others_assigned:
                item["reason"] = _("Others already assigned on this date")
            elif len(people) == 1:
                item["reason"] = _("Only one person available")
            else:
                item["reason"] = _("Back-to-back")
        result.append(item)
    return result
