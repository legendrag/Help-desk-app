from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import time_format
from django.utils.translation import get_language, gettext as _
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.http_cache import apply_read_etag, etag_digest, htmx_not_modified, htmx_revalidation_match
from core.models import Department
from shifts.clock import format_clock
from shifts.access import can_check_in, display_name, has_own_shifts, home_target, is_shift_manager
from shifts.forms import ShiftTypeForm
from shifts.models import DepartmentShiftSettings, ShiftAssignment, ShiftType
from shifts.reports import build_report, report_filename, report_workbook
from shifts.services import (
    CHECKED_IN,
    COMPLETED,
    MISSED,
    NOT_CHECKED_IN,
    ON_SHIFT,
    REPEAT_WEEKS_MAX,
    WORKER_HOURS_LOOKBACK_DAYS,
    WORKER_HOURS_MAX_MINUTES,
    clock_length,
    check_in_marker,
    check_in_opens_at,
    check_in_state,
    check_in_visible,
    effective_crosses_midnight,
    effective_interval,
    settle_check_in,
    effective_times,
    interval_for,
    month_dates,
    neighbor_conflict,
    next_check_in_change,
    night_window_for,
    normalize_start,
    overlap_message,
    overrides_set_by_worker,
    plan_copy,
    saturday_of,
    shift_outcome,
    suggest_nights,
    week_dates,
)

User = get_user_model()


def _forbid():
    return HttpResponseForbidden(_("You cannot open this page."))


def _stale_page():
    """The open page was rendered for someone else (logout, then login as another
    user in another tab). Reload it as the current user instead of 403-ing
    every background refresh."""
    response = HttpResponse(status=204)
    response["HX-Refresh"] = "true"
    return response


def _rendered_for_other_user(request):
    """Background refreshes carry ``u``, the user the page was rendered for."""
    rendered_for = request.GET.get("u")
    return bool(rendered_for) and rendered_for != str(request.user.pk)


def _shell(request, template, context):
    context["is_manager"] = is_shift_manager(request.user)
    context["has_own_shifts"] = has_own_shifts(request.user)
    if request.headers.get("HX-Request"):
        context["base_template"] = "shifts/hx_base.html"
    return render(request, template, context)


@login_required
@require_GET
def shifts_home(request):
    target = home_target(request.user)
    if not target:
        return _forbid()
    return redirect(target)


def _rota_dates(request):
    view = request.POST.get("view") or request.GET.get("view") or "week"
    if view not in ("week", "month"):
        view = "week"
    day = _parse_day(request.POST.get("start") or request.GET.get("start")) or timezone.localdate()
    start = normalize_start(day, view)
    dates = month_dates(start) if view == "month" else week_dates(start)
    return view, start, dates


def _parse_day(raw):
    """A date from a query or form value, or None when it is missing or invalid."""
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def _parse_pk(raw):
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


def _step_start(view, start):
    if view == "month":
        prev_anchor = (start.replace(day=1) - timedelta(days=1)).replace(day=1)
        if start.month == 12:
            next_anchor = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_anchor = start.replace(month=start.month + 1, day=1)
        return prev_anchor, next_anchor
    return start - timedelta(days=7), start + timedelta(days=7)


def _rota_bundle(department, dates):
    first, last = dates[0], dates[-1]
    assignments = list(
        ShiftAssignment.objects.filter(
            shift_type__department=department,
            date__gte=first - timedelta(days=1),
            date__lte=last,
        ).select_related(
            "user",
            "user__role",
            "shift_type",
            "shift_type__department",
            "times_set_by",
            "times_set_by__role",
        )
    )
    visible = [row for row in assignments if first <= row.date <= last]
    now = timezone.now()
    for row in assignments:
        settle_check_in(row, now, save=False)
    for row in visible:
        row.set_by_worker = overrides_set_by_worker(row)
        row.check_marker = check_in_marker(row, now, can_check_in(row.user))
    assigned_ids = {row.user_id for row in visible}
    active = User.objects.filter(
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ).only("id", "username", "first_name", "last_name", "department_id", "user_type", "status")
    extra = User.objects.filter(pk__in=assigned_ids).only(
        "id", "username", "first_name", "last_name", "department_id", "user_type", "status"
    )
    people = {row.pk: row for row in list(active) + list(extra)}
    ordered = sorted(people.values(), key=lambda row: ((row.first_name or ""), row.username))
    by_key = {}
    for row in visible:
        by_key.setdefault((row.user_id, row.date), []).append(row)
    for rows in by_key.values():
        rows.sort(key=lambda row: (effective_interval(row)[0], row.pk))
    for person in ordered:
        person.shift_label = display_name(person)
        person.cells = [(day, by_key.get((person.pk, day), [])) for day in dates]
    return {
        "assignments": assignments,
        "people": ordered,
        "by_key": by_key,
        "dates": dates,
    }


def _rota_etag(department, view, start, assignments):
    max_assignment = max((row.updated_at for row in assignments), default=None)
    max_type = (
        ShiftType.objects.filter(department=department).aggregate(m=Max("updated_at"))["m"]
    )
    return etag_digest([
        get_language(),
        department.pk,
        view,
        start.isoformat(),
        len(assignments),
        max_assignment.isoformat() if max_assignment else "",
        max_type.isoformat() if max_type else "",
        # Page loads settle check-ins in memory only, so a shift ending changes
        # its status without touching updated_at.
        tuple(sorted((row.pk, getattr(row, "check_marker", "")) for row in assignments)),
    ])


def _grid_response(request, department, retarget=False, notice="", skips=None, error=""):
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    etag = _rota_etag(department, view, start, bundle["assignments"])
    if not retarget and htmx_revalidation_match(request, etag):
        return htmx_not_modified(etag)
    prev_start, next_start = _step_start(view, start)
    now = timezone.now()
    check_ins = _open_check_ins(request.user, now)
    my_assignments = [a for a in bundle["assignments"] if a.user_id == request.user.id]
    refresh_in = next_check_in_change(my_assignments, now) if can_check_in(request.user) else None
    context = {
        **bundle,
        "department": department,
        "departments": Department.objects.order_by("name"),
        "view": view,
        "start": start,
        "prev_start": prev_start,
        "next_start": next_start,
        "readonly": False,
        "shell_etag": etag,
        "now": now,
        "today": timezone.localdate(),
        "notice": notice,
        "skips": skips or [],
        "error": error,
        "display_name": display_name,
        "check_ins": check_ins,
        "check_in_sig": _check_in_sig(check_ins),
        "refresh_in": refresh_in,
    }
    template = "shifts/rota_grid.html" if retarget else "shifts/rota.html"
    response = _shell(request, template, context)
    if retarget:
        response["HX-Retarget"] = "#shifts-rota-grid"
        response["HX-Reswap"] = "outerHTML"
    return apply_read_etag(response, etag, request)


@login_required
@require_GET
def shifts_rota(request):
    if not is_shift_manager(request.user):
        return _forbid()
    return _grid_response(request, _types_department(request), retarget=False)


@login_required
@require_GET
def shifts_rota_grid(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    etag = _rota_etag(department, view, start, bundle["assignments"])
    if htmx_revalidation_match(request, etag):
        return htmx_not_modified(etag)
    response = render(request, "shifts/rota_grid.html", {
        **bundle,
        "department": department,
        "view": view,
        "start": start,
        "readonly": False,
        "today": timezone.localdate(),
        "now": timezone.now(),
    })
    return apply_read_etag(response, etag, request)


@login_required
@require_GET
def shifts_mine(request):
    if not has_own_shifts(request.user):
        # Admins and other managers who are not rostered go to the rota instead.
        if is_shift_manager(request.user):
            return redirect("shifts_rota")
        return _forbid()
    today = timezone.localdate()
    lookback = today - timedelta(days=WORKER_HOURS_LOOKBACK_DAYS)
    upcoming = list(
        ShiftAssignment.objects.filter(user=request.user, date__gte=today).select_related(
            "shift_type", "shift_type__department", "times_set_by"
        )
    )
    past_nights = list(
        ShiftAssignment.objects.filter(
            user=request.user,
            shift_type__is_night=True,
            date__gte=lookback,
            date__lt=today,
        ).select_related("shift_type", "shift_type__department", "times_set_by")
    )
    yesterday_shifts = list(
        ShiftAssignment.objects.filter(
            user=request.user,
            date=today - timedelta(days=1),
        ).select_related("shift_type", "shift_type__department", "times_set_by")
    )
    all_recent = {r.pk: r for r in upcoming + past_nights + yesterday_shifts}
    now = timezone.now()
    may_check_in = can_check_in(request.user)
    rows = list(all_recent.values())
    for row in rows:
        settle_check_in(row, now, save=False)
        _decorate_mine(row, now, today, may_check_in)
    rows.sort(key=lambda row: (row.starts_at, row.pk))

    banner_end = None
    for row in rows:
        if row.starts_at <= now < row.ends_at:
            banner_end = row.ends_at
            break

    # A night that started yesterday and is still running belongs with today.
    week_end = saturday_of(today) + timedelta(days=6)
    current = [row for row in rows if row.ends_at > now or row.date >= today]
    current_ids = {row.pk for row in current}
    this_week = [row for row in current if row.date <= week_end]
    later = [row for row in current if row.date > week_end]
    recent = sorted(
        (row for row in rows if row.pk not in current_ids),
        key=lambda row: (row.date, row.pk),
        reverse=True,
    )

    check_ins = _open_check_ins(request.user, now)
    refresh_in = next_check_in_change(rows, now) if may_check_in else None

    return _shell(request, "shifts/mine.html", {
        "check_in_sig": _check_in_sig(check_ins),
        "assignments": rows,
        "this_week": this_week,
        "later": later,
        "recent": recent,
        "banner_end": banner_end,
        "today": today,
        "check_ins": check_ins,
        "refresh_in": refresh_in,
    })


def _length_text(minutes):
    hours, mins = _hours_minutes(minutes)
    if mins:
        return _("%(hours)s hours %(minutes)s minutes") % {"hours": hours, "minutes": mins}
    return _("%(hours)s hours") % {"hours": hours}


def _mine_status(row, now, may_check_in):
    """One word for where this shift stands, as the worker sees it."""
    outcome = shift_outcome(row, now, may_check_in)
    if outcome in (CHECKED_IN, ON_SHIFT):
        return "on_shift"
    if outcome in (COMPLETED, MISSED):
        return outcome
    # Not checked in yet: check-in is open unless a manager cleared it.
    if may_check_in and not row.checked_out_at and now >= check_in_opens_at(row):
        return "open"
    return "not_checked_in" if outcome == NOT_CHECKED_IN else "upcoming"


def _decorate_mine(row, now, today, may_check_in):
    """Attach what one My shifts row shows: status, day label, length, edit rights."""
    start_t, end_t = effective_times(row)
    row.starts_at, row.ends_at = effective_interval(row)
    # Ending at exactly 12:00 AM is the end of this day, not a run into the next one.
    row.ends_next_day = effective_crosses_midnight(start_t, end_t) and end_t != time(0, 0)
    row.length_text = _length_text(clock_length(start_t, end_t)[0])
    row.status = _mine_status(row, now, may_check_in)
    row.is_today = row.date == today
    if row.date == today:
        row.day_label = _("Today")
    elif row.date == today + timedelta(days=1):
        row.day_label = _("Tomorrow")
    elif row.date == today - timedelta(days=1):
        row.day_label = _("Yesterday")
    else:
        row.day_label = ""
    row.set_by_me = overrides_set_by_worker(row)
    # Check-in can change these rows' status while the page is open.
    row.live = today - timedelta(days=1) <= row.date <= today + timedelta(days=1)
    row.can_edit_hours = (
        row.shift_type.is_night
        and row.date >= today - timedelta(days=WORKER_HOURS_LOOKBACK_DAYS)
    )
    return row


@login_required
@require_GET
def shifts_check_in_panels(request):
    if _rendered_for_other_user(request):
        return _stale_page()
    if not has_own_shifts(request.user):
        return _forbid()
    return _check_ins_partial(request)


def _check_ins_partial(request):
    now = timezone.now()
    today = timezone.localdate()
    rows = list(
        ShiftAssignment.objects.filter(
            user=request.user,
            date__in=[today - timedelta(days=1), today, today + timedelta(days=1)],
        ).select_related("shift_type", "user")
    )
    for r in rows:
        settle_check_in(r, now, save=False)
    check_ins = _open_check_ins(request.user, now)
    refresh_in = next_check_in_change(rows, now) if can_check_in(request.user) else None
    banner_end = None
    for row in rows:
        start_dt, end_dt = effective_interval(row)
        if start_dt <= now < end_dt:
            banner_end = end_dt
            break
    return render(request, "shifts/check_ins_partial.html", {
        "check_ins": check_ins,
        "check_in_sig": _check_in_sig(check_ins),
        "banner_end": banner_end,
        "refresh_in": refresh_in,
    })



# Bar states on the Available now timeline, from shifts.services.shift_outcome.
TIMELINE_STATES = {
    CHECKED_IN: "on",
    ON_SHIFT: "on",
    NOT_CHECKED_IN: "late",
    COMPLETED: "done",
    MISSED: "missed",
}
TIMELINE_TICK_HOURS = range(0, 24, 3)


def _timeline_percent(moment, day_start, day_length):
    offset = (moment - day_start).total_seconds() / day_length
    return round(min(max(offset, 0.0), 1.0) * 100, 3)


def _available_board(request):
    """Today's shifts, one row per person, grouped by department.

    The day runs from local midnight to midnight. Last night's shifts still
    running and tonight's shifts that end tomorrow are clipped at the edges.
    """
    now = timezone.now()
    today = timezone.localdate()
    # Not aware_on(): Egypt's DST starts at midnight, so 00:00 can be missing.
    day_start = timezone.make_aware(datetime.combine(today, time.min))
    day_end = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min))
    day_length = (day_end - day_start).total_seconds()
    rows = list(
        ShiftAssignment.objects.filter(date__in=[today - timedelta(days=1), today])
        .select_related("user", "user__role", "shift_type", "shift_type__department")
    )
    uses_check_in = {}
    people = {}
    for row in rows:
        settle_check_in(row, now, save=False)
        start_dt, end_dt = effective_interval(row)
        if end_dt <= day_start or start_dt >= day_end:
            continue
        if row.user_id not in uses_check_in:
            uses_check_in[row.user_id] = can_check_in(row.user)
        # An early check-in is not on shift yet; it starts at the shift start.
        outcome = shift_outcome(row, now, uses_check_in[row.user_id])
        state = "later" if now < start_dt else TIMELINE_STATES.get(outcome, "later")
        left = _timeline_percent(start_dt, day_start, day_length)
        key = (row.shift_type.department_id, row.user_id)
        person = people.setdefault(key, {"name": display_name(row.user), "bars": []})
        person["bars"].append({
            "shift_type": row.shift_type,
            "start": start_dt,
            "end": end_dt,
            "state": state,
            "left": left,
            "width": max(round(_timeline_percent(end_dt, day_start, day_length) - left, 3), 0.5),
            "clipped_start": start_dt < day_start,
            "clipped_end": end_dt > day_end,
        })
    order = {"on": 0, "late": 1, "later": 2, "done": 3, "missed": 3}
    by_department = {}
    for (department_id, _user_id), person in people.items():
        person["bars"].sort(key=lambda bar: bar["start"])
        person["on"] = any(bar["state"] == "on" for bar in person["bars"])
        first = min(person["bars"], key=lambda bar: (order[bar["state"]], bar["start"]))
        person["rank"] = (order[first["state"]], first["start"], person["name"].casefold())
        person["status"] = first["state"]
        by_department.setdefault(department_id, []).append(person)
    cards = []
    for department in Department.objects.order_by("name"):
        members = sorted(by_department.get(department.pk, []), key=lambda person: person["rank"])
        cards.append({
            "department": department,
            "people": members,
            "on_count": sum(1 for person in members if person["on"]),
        })
    # Departments with someone on now first, then any scheduled today, then the rest.
    cards.sort(key=lambda card: (not card["on_count"], not card["people"]))
    show_types = _shows_shift_types(request.user)
    parts = [get_language(), show_types, today.isoformat()]
    for card in cards:
        for person in card["people"]:
            for bar in person["bars"]:
                parts.append((
                    card["department"].pk, person["name"], bar["state"],
                    bar["start"].isoformat(), bar["end"].isoformat(),
                    bar["shift_type"].name, bar["shift_type"].colour,
                ))
    timeline = {
        "day_start": day_start,
        "day_end": day_end,
        "now": _timeline_percent(now, day_start, day_length),
        "now_label": format_clock(now),
        "time_zone": timezone.get_current_timezone_name(),
        "ticks": [
            {
                "label": format_clock(time(hour, 0)),
                "short": time_format(time(hour, 0), "g A"),
                "left": round(hour / 24 * 100, 3),
                "major": hour % 6 == 0,
                "edge": hour == 0,
            }
            for hour in TIMELINE_TICK_HOURS
        ],
    }
    return cards, timeline, etag_digest(parts)


@login_required
@require_GET
def shifts_available(request):
    cards, timeline, etag = _available_board(request)
    return _shell(request, "shifts/available.html", _available_context(request, cards, timeline, etag))


@login_required
@require_GET
def shifts_available_board(request):
    cards, timeline, etag = _available_board(request)
    if htmx_revalidation_match(request, etag):
        request.ticket_list_304_defer_session_save = True
        return htmx_not_modified(etag)
    response = render(request, "shifts/available_board.html", _available_context(request, cards, timeline, etag))
    return apply_read_etag(response, etag, request)


def _shows_shift_types(user) -> bool:
    """Branch staff see who is on, never which shift type they are on."""
    return getattr(user, "user_type", "") != User.UserType.BRANCH


def _available_context(request, cards, timeline, etag):
    return {
        "cards": cards,
        "timeline": timeline,
        "board_etag": etag,
        "show_shift_type": _shows_shift_types(request.user),
        "on_shift_total": sum(card["on_count"] for card in cards),
        "anyone_scheduled": any(card["people"] for card in cards),
        "unscheduled": [card["department"] for card in cards if not card["people"]],
    }


def _department_or_404(raw):
    pk = _parse_pk(raw)
    if pk is None:
        raise Http404(_("No department exists."))
    return get_object_or_404(Department, pk=pk)


def _selected_department(request):
    raw = request.POST.get("department") or request.GET.get("department")
    if raw:
        return _department_or_404(raw)
    department = Department.objects.order_by("name").first()
    if department is None:
        raise Http404(_("No department exists."))
    return department


@login_required
@require_http_methods(["GET", "POST"])
def shifts_type_add(request):
    if not is_shift_manager(request.user):
        return _forbid()
    form = ShiftTypeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        if request.headers.get("HX-Request"):
            response = _render_types(request)
            response["HX-Retarget"] = "#shell-content"
            response["HX-Reswap"] = "innerHTML"
            response["HX-Trigger"] = "closeModal"
            return response
        query = urlencode({"department": saved.department_id})
        return redirect(f"{reverse('shifts_types')}?{query}")
    return _type_form_response(request, form)


@login_required
@require_http_methods(["GET", "POST"])
def shifts_type_edit(request, pk):
    if not is_shift_manager(request.user):
        return _forbid()
    row = get_object_or_404(ShiftType, pk=pk)
    form = ShiftTypeForm(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        if request.headers.get("HX-Request"):
            response = _render_types(request)
            response["HX-Retarget"] = "#shell-content"
            response["HX-Reswap"] = "innerHTML"
            response["HX-Trigger"] = "closeModal"
            return response
        query = urlencode({"department": saved.department_id})
        return redirect(f"{reverse('shifts_types')}?{query}")
    return _type_form_response(request, form, editing=True)


def _type_form_response(request, form, editing=False):
    context = {"form": form, "editing": editing}
    if request.headers.get("HX-Request"):
        return render(request, "shifts/type_form.html", context)
    # Opened directly (a bookmark or a new tab): the same form as a full page.
    context["active_tab"] = "shifts_types"
    return _shell(request, "shifts/type_form_page.html", context)


@login_required
@require_POST
def shifts_type_archive(request, pk):
    if not is_shift_manager(request.user):
        return _forbid()
    row = get_object_or_404(ShiftType, pk=pk)
    row.archived = True
    row.save()
    return redirect("shifts_types")


def _department_with_shift_types():
    return (
        Department.objects.filter(shift_types__isnull=False)
        .distinct()
        .order_by("name")
        .first()
    )


def _types_department(request):
    raw = request.POST.get("department") or request.GET.get("department")
    if raw:
        return _department_or_404(raw)
    return _department_with_shift_types() or _selected_department(request)


def _render_types(request, night_error="", typed=None):
    department = _types_department(request)
    saved_starts, saved_ends = night_window_for(department)
    typed = typed or {}
    rows = (
        ShiftType.objects.filter(department=department)
        .select_related("department")
        .order_by("archived", "name")
    )
    return _shell(request, "shifts/types.html", {
        "department": department,
        "types": rows,
        "departments": Department.objects.order_by("name"),
        "night_starts_value": typed.get("starts", saved_starts.strftime("%H:%M")),
        "night_ends_value": typed.get("ends", saved_ends.strftime("%H:%M")),
        "night_error": night_error,
        # Also rendered after add/edit/night-start posts, whose URL names differ.
        "active_tab": "shifts_types",
    })


@login_required
@require_GET
def shifts_types(request):
    if not is_shift_manager(request.user):
        return _forbid()
    return _render_types(request)


@login_required
@require_POST
def shifts_night_starts(request):
    """Save the department's night window, then recompute its shift types."""
    if not is_shift_manager(request.user):
        return _forbid()
    department = _department_or_404(request.POST.get("department"))
    current_starts, current_ends = night_window_for(department)
    try:
        starts = _parse_clock(request.POST.get("night_starts_at")) or current_starts
        ends = _parse_clock(request.POST.get("night_ends_at")) or current_ends
    except _BadClock:
        starts = ends = None
    if starts is None or ends is None or starts == ends:
        typed = {
            "starts": (request.POST.get("night_starts_at") or "").strip(),
            "ends": (request.POST.get("night_ends_at") or "").strip(),
        }
        return _render_types(request, _("Enter a night start and a night end that differ."), typed)
    settings, _created = DepartmentShiftSettings.objects.get_or_create(department=department)
    settings.night_starts_at = time(starts.hour, starts.minute)
    settings.night_ends_at = time(ends.hour, ends.minute)
    settings.save(update_fields=["night_starts_at", "night_ends_at", "updated_at"])
    department._night_window = (settings.night_starts_at, settings.night_ends_at)
    for row in ShiftType.objects.filter(department=department):
        row.department = department
        row.save()
    if request.headers.get("HX-Request"):
        response = _render_types(request)
        response["HX-Retarget"] = "#shell-content"
        response["HX-Reswap"] = "innerHTML"
        return response
    query = urlencode({"department": department.pk})
    return redirect(f"{reverse('shifts_types')}?{query}")


class _BadClock(ValueError):
    pass


def _parse_clock(raw):
    """A wall-clock time, None when blank. Raises _BadClock for garbage like 99:00."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return time.fromisoformat(raw)
    except ValueError as exc:
        raise _BadClock(raw) from exc


def _cell_existing(user, on, request):
    rows = list(
        ShiftAssignment.objects.filter(user=user, date=on).select_related("shift_type")
    )
    raw = request.POST.get("assignment") or request.GET.get("assignment")
    if raw:
        pk = _parse_pk(raw)
        if pk is None:
            raise Http404(_("That shift no longer exists."))
        for row in rows:
            if row.pk == pk:
                return row
        return get_object_or_404(ShiftAssignment, pk=pk, user=user, date=on)
    if request.method == "GET":
        return None
    shift_type_id = request.POST.get("shift_type") or ""
    editing_action = (
        request.POST.get("clear_check_in") == "1"
        or request.POST.get("restore_check_in") == "1"
        or request.POST.get("reset_times") == "1"
        or not shift_type_id
    )
    if editing_action and len(rows) == 1:
        return rows[0]
    matches = [row for row in rows if shift_type_id and str(row.shift_type_id) == str(shift_type_id)]
    if len(matches) == 1:
        return matches[0]
    return None


@login_required
@require_http_methods(["GET", "POST"])
def shifts_cell(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    user_pk = _parse_pk(request.POST.get("user") or request.GET.get("user"))
    on = _parse_day(request.POST.get("date") or request.GET.get("date"))
    if user_pk is None or on is None:
        raise Http404(_("That shift no longer exists."))
    user = get_object_or_404(User, pk=user_pk)
    existing = _cell_existing(user, on, request)
    now = timezone.now()
    if existing:
        settle_check_in(existing, now, save=request.method == "POST")
    if request.method == "GET":
        if not request.headers.get("HX-Request"):
            # The dialog only works inside the rota; a direct visit goes to that week.
            return _rota_redirect(request, department, "week", normalize_start(on, "week"))
        return _cell_form(request, department, user, on, existing, now)
    if request.method == "POST" and request.POST.get("clear_check_in") == "1":
        if existing and existing.checked_in_at:
            existing.checked_in_at = None
            existing.checked_out_at = now
            existing.save(update_fields=["checked_in_at", "checked_out_at", "updated_at"])
        response = _grid_response(request, department, retarget=True)
        response["HX-Trigger"] = "closeModal"
        return response
    if request.method == "POST" and request.POST.get("restore_check_in") == "1":
        if existing and _can_restore_check_in(existing, now):
            existing.checked_in_at = now
            existing.checked_out_at = None
            existing.arrived_at = existing.arrived_at or now
            existing.save(update_fields=["checked_in_at", "checked_out_at", "arrived_at", "updated_at"])
        response = _grid_response(request, department, retarget=True)
        response["HX-Trigger"] = "closeModal"
        return response
    shift_type_id = request.POST.get("shift_type") or ""
    if not shift_type_id:
        if existing:
            existing.delete()
        response = _grid_response(request, department, retarget=True)
        response["HX-Trigger"] = "closeModal"
        return response
    if _parse_pk(shift_type_id) is None:
        raise Http404(_("That shift no longer exists."))
    shift_type = get_object_or_404(ShiftType, pk=int(shift_type_id), department=department)
    if request.POST.get("reset_times") == "1" and existing:
        existing.start_time_override = None
        existing.end_time_override = None
        existing.times_set_by = None
        existing.times_set_at = None
        existing.save()
        response = _grid_response(request, department, retarget=True)
        response["HX-Trigger"] = "closeModal"
        return response
    error = None
    try:
        start_t = _parse_clock(request.POST.get("start_time_override"))
        end_t = _parse_clock(request.POST.get("end_time_override"))
    except _BadClock:
        start_t = end_t = None
        error = _("Enter a valid time.")
    if error:
        pass
    elif (start_t is None) ^ (end_t is None):
        error = _("Enter both start and end, or leave both blank.")
    elif start_t is not None and end_t is not None and start_t == end_t:
        error = _("Start and end must differ.")
    else:
        changing_user = existing is None or existing.user_id != user.pk
        if on >= timezone.localdate() or changing_user:
            if (
                user.user_type != User.UserType.SUPPORT
                or user.status != User.Status.ACTIVE
                or user.department_id != shift_type.department_id
            ):
                error = _("Only active support users in this department can be assigned.")
        if error is None and on >= timezone.localdate() and shift_type.archived:
            error = _("Archived shift types cannot be assigned.")
    if error is None:
        use_start = start_t if start_t is not None else shift_type.start_time
        use_end = end_t if end_t is not None else shift_type.end_time
        probe = existing or ShiftAssignment(user=user, date=on, shift_type=shift_type)
        try:
            start_dt, end_dt = interval_for(on, use_start, use_end)
        except ValueError as exc:
            error = str(exc)
        else:
            other = neighbor_conflict(probe, start_dt, end_dt, exclude_pk=getattr(existing, "pk", None))
            if other:
                error = overlap_message(other)
            elif ShiftAssignment.objects.filter(
                user=user, date=on, shift_type=shift_type
            ).exclude(pk=getattr(existing, "pk", None)).exists():
                error = _("This shift is already on that day.")
    if error:
        return _cell_form(
            request, department, user, on, existing, now,
            error=error,
            selected_type=shift_type.pk,
            start_value=(request.POST.get("start_time_override") or "").strip(),
            end_value=(request.POST.get("end_time_override") or "").strip(),
        )
    row = existing or ShiftAssignment(user=user, date=on)
    type_changed = bool(existing and existing.shift_type_id != shift_type.pk)
    row.shift_type = shift_type
    if start_t is not None and end_t is not None:
        row.start_time_override = start_t
        row.end_time_override = end_t
        row.times_set_by = request.user
        row.times_set_at = timezone.now()
    if type_changed:
        row.checked_in_at = None
        row.checked_out_at = None
        row.arrived_at = None
    row.save()
    response = _grid_response(request, department, retarget=True)
    response["HX-Trigger"] = "closeModal"
    return response


def _cell_form(request, department, user, on, existing, now, *, error="", selected_type=None,
               start_value=None, end_value=None):
    """The add/edit dialog. After an error it keeps what the manager picked and typed."""
    if selected_type is None and existing:
        selected_type = existing.shift_type_id
    if start_value is None:
        start_value = existing.start_time_override.strftime("%H:%M") if existing and existing.start_time_override else ""
    if end_value is None:
        end_value = existing.end_time_override.strftime("%H:%M") if existing and existing.end_time_override else ""
    return render(request, "shifts/cell_form.html", {
        "department": department,
        "person": user,
        "on": on,
        "existing": existing,
        "types": ShiftType.objects.filter(department=department, archived=False),
        "can_restore": _can_restore_check_in(existing, now),
        "error": error,
        "selected_type": selected_type,
        "start_value": start_value,
        "end_value": end_value,
    })


def _write_planned(planned):
    created = 0
    skips = []
    for item in sorted(planned, key=lambda row: row["date"]):
        if item["skip"]:
            skips.append(item)
            continue
        if ShiftAssignment.objects.filter(
            user_id=item["user_id"],
            date=item["date"],
            shift_type_id=item["shift_type_id"],
        ).exists():
            item["skip"] = "already assigned"
            skips.append(item)
            continue
        shift_type = ShiftType.objects.get(pk=item["shift_type_id"])
        probe = ShiftAssignment(user_id=item["user_id"], date=item["date"], shift_type=shift_type)
        start_t = item["start"] if item["start"] is not None else shift_type.start_time
        end_t = item["end"] if item["end"] is not None else shift_type.end_time
        start_dt, end_dt = interval_for(item["date"], start_t, end_t)
        other = neighbor_conflict(probe, start_dt, end_dt)
        if other:
            item["skip"] = "overlaps"
            skips.append(item)
            continue
        ShiftAssignment.objects.create(
            user_id=item["user_id"],
            date=item["date"],
            shift_type=shift_type,
            start_time_override=item["start"],
            end_time_override=item["end"],
            times_set_by_id=item["times_set_by_id"],
            times_set_at=item["times_set_at"],
            checked_in_at=None,
        )
        created += 1
    return created, skips


@login_required
@require_POST
def shifts_copy_week(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    start = normalize_start(_parse_day(request.POST.get("start")) or timezone.localdate(), "week")
    source_dates = week_dates(start - timedelta(days=7))
    source_rows = list(
        ShiftAssignment.objects.filter(
            shift_type__department=department,
            date__gte=source_dates[0],
            date__lte=source_dates[-1],
        ).select_related("shift_type", "times_set_by", "times_set_by__role")
    )
    with transaction.atomic():
        created, skips = _write_planned(plan_copy(source_rows, timedelta(days=7), request.user))
    if created == 0 and not skips:
        notice = _("Nothing to copy.")
    else:
        notice = _("Copied %(count)s shifts.") % {"count": created}
    return _rota_action(request, department, notice, skips=skips, refresh_grid=True)


@login_required
@require_POST
def shifts_repeat_week(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    start = normalize_start(_parse_day(request.POST.get("start")) or timezone.localdate(), "week")
    try:
        weeks = int(request.POST.get("weeks") or "")
    except ValueError:
        weeks = 0
    if weeks < 1 or weeks > REPEAT_WEEKS_MAX:
        return _rota_action(
            request,
            department,
            _("Enter a number of weeks from 1 to 12."),
            error=True,
        )
    source_rows = list(
        ShiftAssignment.objects.filter(
            shift_type__department=department,
            date__gte=start,
            date__lte=start + timedelta(days=6),
        ).select_related("shift_type", "times_set_by", "times_set_by__role")
    )
    created = 0
    skips = []
    with transaction.atomic():
        for k in range(1, weeks + 1):
            made, skipped = _write_planned(plan_copy(source_rows, timedelta(days=7 * k), request.user))
            created += made
            skips.extend(skipped)
            source_rows = list(
                ShiftAssignment.objects.filter(
                    shift_type__department=department,
                    date__gte=start,
                    date__lte=start + timedelta(days=6),
                ).select_related("shift_type", "times_set_by", "times_set_by__role")
            )
    notice = _("Repeated %(count)s shifts.") % {"count": created}
    return _rota_action(request, department, notice, skips=skips, refresh_grid=True)


def _dates_inclusive(start, end):
    if end < start:
        start, end = end, start
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _people_and_existing(people):
    by_user = {person.pk: [] for person in people}
    rows = ShiftAssignment.objects.filter(user__in=people).select_related("shift_type", "user")
    for row in rows:
        by_user.setdefault(row.user_id, []).append(row)
    return by_user


def _apply_rotation(proposals, shift_type, department):
    created = 0
    skips = []
    with transaction.atomic():
        for item in proposals:
            if item.get("gap"):
                continue
            user = User.objects.filter(pk=item["user_id"]).select_related("role").first()
            if user is not None:
                item["name"] = display_name(user)
            if (
                user is None
                or user.user_type != User.UserType.SUPPORT
                or user.status != User.Status.ACTIVE
                or user.department_id != department.pk
            ):
                item["skip"] = _("Only active support users in this department can be assigned.")
                skips.append(item)
                continue
            if shift_type.archived or not shift_type.is_night or shift_type.department_id != department.pk:
                item["skip"] = _("Archived shift types cannot be assigned.")
                skips.append(item)
                continue
            if ShiftAssignment.objects.filter(
                user_id=user.pk, date=item["date"], shift_type=shift_type
            ).exists():
                item["skip"] = "already assigned"
                skips.append(item)
                continue
            probe = ShiftAssignment(user=user, date=item["date"], shift_type=shift_type)
            start_dt, end_dt = interval_for(item["date"], shift_type.start_time, shift_type.end_time)
            other = neighbor_conflict(probe, start_dt, end_dt)
            if other:
                item["skip"] = overlap_message(other)
                skips.append(item)
                continue
            ShiftAssignment.objects.create(
                user=user,
                shift_type=shift_type,
                date=item["date"],
                start_time_override=None,
                end_time_override=None,
                times_set_by=None,
                times_set_at=None,
                checked_in_at=None,
            )
            created += 1
    return created, skips


def _rotation_choices(department):
    if department is None:
        return [], []
    night_types = list(
        ShiftType.objects.filter(department=department, archived=False, is_night=True).order_by("name")
    )
    people = list(User.objects.filter(
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ).order_by("first_name", "last_name", "username"))
    for person in people:
        person.shift_label = display_name(person)
    return night_types, people


def _attach_names(rows, people=()):
    names = {person.pk: display_name(person) for person in people}
    missing = [
        row.get("user_id")
        for row in rows
        if row.get("user_id") and row["user_id"] not in names and not row.get("name")
    ]
    if missing:
        for user in User.objects.filter(pk__in=set(missing)):
            names[user.pk] = display_name(user)
    for row in rows:
        user_id = row.get("user_id")
        if user_id and not row.get("name"):
            row["name"] = names.get(user_id, "")
    return rows


def _posted_night_type(request, department):
    raw = (request.POST.get("shift_type") or "").strip()
    if not raw.isdigit():
        raise Http404(_("Archived shift types cannot be assigned."))
    return get_object_or_404(
        ShiftType, pk=int(raw), department=department, archived=False, is_night=True,
    )


def _posted_dates(request):
    try:
        start = date.fromisoformat(request.POST.get("start") or "")
        end = date.fromisoformat(request.POST.get("end") or "")
    except ValueError:
        return None, None
    return start, end


@login_required
@require_POST
def shifts_calc_rotation(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    shift_type = _posted_night_type(request, department)
    start, end = _posted_dates(request)
    if start is None or end is None:
        return render(request, "shifts/calc_rotation.html", {
            "proposals": [],
            "skips": [],
            "created": 0,
            "department": department,
            "shift_type": shift_type,
            "error": _("Enter a start and an end date."),
        })
    dates = _dates_inclusive(start, end)
    people = list(User.objects.filter(
        pk__in=[pk for pk in map(_parse_pk, request.POST.getlist("users")) if pk is not None],
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ))
    proposals = suggest_nights(people, dates, shift_type, _people_and_existing(people))
    created = 0
    skips = []
    if request.POST.get("action") == "apply":
        for person in people:
            for day in dates:
                if ShiftAssignment.objects.filter(user=person, date=day, shift_type=shift_type).exists():
                    skips.append({
                        "date": day,
                        "user_id": person.pk,
                        "name": display_name(person),
                        "skip": "already assigned",
                    })
        created, applied_skips = _apply_rotation(
            [item for item in proposals if not item.get("gap")],
            shift_type,
            department,
        )
        skips.extend(applied_skips)
    _attach_names(proposals, people)
    _attach_names(skips, people)
    return render(request, "shifts/calc_rotation.html", {
        "proposals": proposals,
        "skips": skips,
        "created": created,
        "department": department,
        "shift_type": shift_type,
    })


def _rota_redirect(request, department, view, start, message=None, *, error=False):
    if message:
        if error:
            messages.error(request, message)
        else:
            messages.success(request, message)
    query = urlencode({
        "department": department.pk,
        "view": view,
        "start": start.isoformat(),
    })
    return redirect(f"{reverse('shifts_rota')}?{query}")


def _skip_text(skips):
    parts = []
    for item in skips:
        day = item["date"].isoformat() if hasattr(item.get("date"), "isoformat") else item.get("date", "")
        parts.append(f"{item.get('name') or ''} {day} {item.get('skip') or ''}".strip())
    return " ".join(part for part in parts if part)


def _rota_action(request, department, message, *, error=False, skips=None, people=(), refresh_grid=False):
    """HX requests get a fragment. A normal POST goes back to the rota."""
    view, start, dates = _rota_dates(request)
    named = _attach_names(list(skips or []), people)
    if not request.headers.get("HX-Request"):
        extra = _skip_text(named)
        text = f"{message} {extra}".strip() if extra else message
        return _rota_redirect(request, department, view, start, text, error=error)
    context = {
        "notice": "" if error else message,
        "error": message if error else "",
        "skips": named,
        "grid_oob": False,
    }
    if refresh_grid:
        context.update({
            **_rota_bundle(department, dates),
            "department": department,
            "readonly": False,
            "today": timezone.localdate(),
            "now": timezone.now(),
            "grid_oob": True,
        })
    return render(request, "shifts/action_result.html", context)


def _open_night_dates(department, dates):
    today = timezone.localdate()
    taken = set(
        ShiftAssignment.objects.filter(
            shift_type__department=department,
            shift_type__is_night=True,
            date__in=dates,
            date__gte=today,
        ).values_list("date", flat=True)
    )
    open_dates = []
    skips = []
    for day in dates:
        if day < today:
            skips.append({"date": day, "skip": _("skipped (past)")})
        elif day in taken:
            skips.append({"date": day, "skip": _("skipped (already assigned)")})
        else:
            open_dates.append(day)
    return open_dates, skips


@login_required
@require_POST
def shifts_auto_fill(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    view, start, dates = _rota_dates(request)
    htmx = bool(request.headers.get("HX-Request"))
    night_types = list(
        ShiftType.objects.filter(department=department, archived=False, is_night=True).order_by("name")
    )
    if not night_types:
        return _rota_action(request, department, _("This department has no night shift."))
    chosen_id = (request.POST.get("shift_type") or "").strip()
    if chosen_id:
        shift_type = next((row for row in night_types if str(row.pk) == chosen_id), None)
        if shift_type is None:
            return _rota_action(
                request,
                department,
                _("Choose a night shift type on the rota."),
                error=True,
            )
    elif len(night_types) > 1:
        if not htmx:
            return _rota_redirect(
                request, department, view, start, _("Choose a night shift type on the rota."), error=True,
            )
        return render(request, "shifts/calc_rotation.html", {
            "pick_types": night_types,
            "department": department,
            "proposals": [],
            "skips": [],
            "created": 0,
        })
    else:
        shift_type = night_types[0]
    people = list(User.objects.filter(
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ))
    if not people:
        return _rota_action(request, department, _("This department has no one to assign."))
    open_dates, skipped = _open_night_dates(department, dates)
    proposals = suggest_nights(people, open_dates, shift_type, _people_and_existing(people))
    _attach_names(proposals, people)
    if request.POST.get("action") != "apply":
        if not htmx:
            return _rota_redirect(
                request, department, view, start, _("Open the rota to review the night rotation."),
            )
        return render(request, "shifts/calc_rotation.html", {
            "proposals": proposals,
            "skips": skipped,
            "created": 0,
            "department": department,
            "shift_type": shift_type,
            "can_apply": True,
        })
    created, applied = _apply_rotation(proposals, shift_type, department)
    skips = skipped + applied
    _attach_names(skips, people)
    notice = _("Filled %(count)s night shifts.") % {"count": created}
    return _rota_action(request, department, notice, skips=skips, people=people, refresh_grid=True)


def _hours_minutes(minutes):
    return minutes // 60, minutes % 60


@login_required
@require_GET
def shifts_calculator(request):
    if not is_shift_manager(request.user):
        return _forbid()
    raw = request.GET.get("department")
    department = _department_or_404(raw) if raw else _department_with_shift_types()
    if department is None:
        department = Department.objects.order_by("name").first()
    night_types, people = _rotation_choices(department)
    context = {
        "departments": Department.objects.order_by("name"),
        "department": department,
        "night_types": night_types,
        "people": people,
    }
    if request.GET.get("part") == "rotation":
        return render(request, "shifts/calculator_rotation_options.html", context)
    context["work_people"] = _work_hours_people(department)
    if request.GET.get("part") == "work_people":
        context["reset_result"] = True
        return render(request, "shifts/calc_work_people.html", context)
    first, last = _this_month()
    context.update({"work_start": first, "work_end": last})
    return _shell(request, "shifts/calculator.html", context)


def _this_month():
    first = timezone.localdate().replace(day=1)
    return first, month_dates(first)[-1]


def _work_hours_people(department):
    """Support staff in one department for the work hours report, inactive ones last."""
    if department is None:
        return []
    people = list(
        User.objects.filter(user_type=User.UserType.SUPPORT, department=department)
        .order_by("first_name", "last_name", "username")
    )
    people.sort(key=lambda person: person.status != User.Status.ACTIVE)
    for person in people:
        person.shift_label = display_name(person)
    return people


def _work_hours_request(request):
    """Person, date range and shift filter from the query string."""
    person_pk = _parse_pk(request.GET.get("person"))
    person = None
    if person_pk is not None:
        person = (
            User.objects.filter(pk=person_pk, user_type=User.UserType.SUPPORT)
            .select_related("role", "department")
            .first()
        )
    first, last = _this_month()
    start = _parse_day(request.GET.get("start")) or first
    end = _parse_day(request.GET.get("end")) or last
    night_only = request.GET.get("shifts") == "night"
    return person, start, end, night_only


@login_required
@require_GET
def shifts_calc_work(request):
    """One person's shifts in a date range, laid out like the paper statement."""
    if not is_shift_manager(request.user):
        return _forbid()
    person, start, end, night_only = _work_hours_request(request)
    if person is None:
        return render(request, "shifts/calc_work.html", {"error": _("Choose a person.")})
    report = build_report(person, start, end, night_only)
    export_query = urlencode({
        "person": person.pk,
        "start": report.start.isoformat(),
        "end": report.end.isoformat(),
        "shifts": "night" if night_only else "all",
    })
    return render(request, "shifts/calc_work.html", {
        "report": report,
        "export_url": f"{reverse('shifts_calc_work_export')}?{export_query}",
    })


@login_required
@require_GET
def shifts_calc_work_export(request):
    """The same report as an Excel file."""
    if not is_shift_manager(request.user):
        return _forbid()
    person, start, end, night_only = _work_hours_request(request)
    if person is None:
        raise Http404(_("Choose a person."))
    report = build_report(person, start, end, night_only)
    response = HttpResponse(
        report_workbook(report),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{report_filename(report)}"'
    return response


@login_required
@require_GET
def shifts_calc_length(request):
    if not is_shift_manager(request.user):
        return _forbid()
    raw_start = request.GET.get("start", "")
    raw_end = request.GET.get("end", "")
    if not raw_start or not raw_end:
        return render(request, "shifts/calc_length.html", {})
    try:
        start_t = time.fromisoformat(raw_start)
        end_t = time.fromisoformat(raw_end)
    except ValueError:
        start_t = end_t = None
    if start_t is None or end_t is None or start_t == end_t:
        return render(request, "shifts/calc_length.html", {"error": _("Start and end must differ.")})
    total, after = clock_length(start_t, end_t)
    hours, minutes = _hours_minutes(total)
    after_hours, after_minutes = _hours_minutes(after)
    return render(request, "shifts/calc_length.html", {
        "total_text": _("%(hours)s hours %(minutes)s minutes") % {"hours": hours, "minutes": minutes},
        "after_text": _("%(hours)s hours %(minutes)s minutes after midnight.") % {
            "hours": after_hours,
            "minutes": after_minutes,
        },
    })


@login_required
@require_http_methods(["GET", "POST"])
def shifts_mine_hours(request, pk):
    assignment = get_object_or_404(
        ShiftAssignment.objects.select_related("shift_type", "user"),
        pk=pk,
    )
    if assignment.user_id != request.user.id:
        return _forbid()
    if not assignment.shift_type.is_night:
        return _forbid()
    if not has_own_shifts(request.user):
        return _forbid()
    today = timezone.localdate()
    if assignment.date < today - timedelta(days=WORKER_HOURS_LOOKBACK_DAYS):
        return _mine_hours_form(request, assignment, _("You can only change hours from the last 7 days onward."))
    if request.method == "GET":
        if not request.headers.get("HX-Request"):
            # The dialog only works inside My shifts; a direct visit goes there.
            return redirect("shifts_mine")
        return _mine_hours_form(request, assignment)
    if request.POST.get("action") == "reset":
        assignment.start_time_override = None
        assignment.end_time_override = None
        assignment.times_set_by = None
        assignment.times_set_at = None
        assignment.save()
        return _mine_row(request, assignment)
    start_raw = (request.POST.get("start_time") or "").strip()
    end_raw = (request.POST.get("end_time") or "").strip()
    typed = {"start": start_raw, "end": end_raw}
    if not start_raw or not end_raw:
        return _mine_hours_form(request, assignment, _("Enter both a start and an end time."), typed)
    try:
        start_t = _parse_clock(start_raw)
        end_t = _parse_clock(end_raw)
    except _BadClock:
        return _mine_hours_form(request, assignment, _("Enter a valid time."), typed)
    total, _after = clock_length(start_t, end_t)
    if total <= 0 or total > WORKER_HOURS_MAX_MINUTES:
        return _mine_hours_form(
            request, assignment,
            _("This shift must be longer than 0 hours and no more than 16 hours."), typed,
        )
    try:
        start_dt, end_dt = interval_for(assignment.date, start_t, end_t)
    except ValueError as exc:
        return _mine_hours_form(request, assignment, str(exc), typed)
    other = neighbor_conflict(assignment, start_dt, end_dt, exclude_pk=assignment.pk)
    if other:
        return _mine_hours_form(request, assignment, overlap_message(other), typed)
    assignment.start_time_override = start_t
    assignment.end_time_override = end_t
    assignment.times_set_by = request.user
    assignment.times_set_at = timezone.now()
    assignment.save()
    return _mine_row(request, assignment)


@login_required
@require_GET
def shifts_team(request):
    if request.user.user_type != "support" and not is_shift_manager(request.user):
        return _forbid()
    if is_shift_manager(request.user):
        department = _types_department(request)
    else:
        requested = request.GET.get("department")
        if requested and str(request.user.department_id) != str(requested):
            return _forbid()
        if not request.user.department_id:
            return _shell(request, "shifts/team.html", {
                "error": _("You are not assigned to a department."),
                "readonly": True,
            })
        department = request.user.department
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    return _shell(request, "shifts/team.html", {
        **bundle,
        "department": department,
        "departments": Department.objects.order_by("name"),
        "view": view,
        "start": start,
        "readonly": True,
        "today": timezone.localdate(),
        "now": timezone.now(),
    })


@login_required
@require_GET
def shifts_mine_row(request, pk):
    """One My shifts row, re-fetched when a check-in changes its status."""
    assignment = get_object_or_404(
        ShiftAssignment.objects.select_related("shift_type", "shift_type__department", "times_set_by", "user"),
        pk=pk,
    )
    if assignment.user_id != request.user.id:
        # A row only refreshes in the background, from a page left open.
        return _stale_page() if request.headers.get("HX-Request") else _forbid()
    now = timezone.now()
    settle_check_in(assignment, now, save=False)
    _decorate_mine(assignment, now, timezone.localdate(), can_check_in(request.user))
    return render(request, "shifts/mine_row.html", {"assignment": assignment})


def _mine_hours_form(request, assignment, error="", typed=None):
    """The Edit hours dialog. After an error the inputs keep what the worker typed."""
    start_t, end_t = effective_times(assignment)
    typed = typed or {}
    return render(request, "shifts/mine_hours_form.html", {
        "assignment": assignment,
        "error": error,
        "start_value": typed.get("start", start_t.strftime("%H:%M")),
        "end_value": typed.get("end", end_t.strftime("%H:%M")),
    })


def _mine_row(request, assignment):
    """The saved row, swapped in place of the old one; the dialog closes.

    The check-in list reloads too, since the shift's times (and so its
    check-in window) may have moved.
    """
    now = timezone.now()
    _decorate_mine(assignment, now, timezone.localdate(), can_check_in(request.user))
    response = render(request, "shifts/mine_row.html", {"assignment": assignment})
    response["HX-Retarget"] = f"#shift-mine-{assignment.pk}"
    response["HX-Reswap"] = "outerHTML"
    response["HX-Trigger"] = "closeModal, shiftsChanged"
    return response


def _can_restore_check_in(assignment, now) -> bool:
    if assignment is None:
        return False
    if assignment.checked_in_at or not assignment.checked_out_at:
        return False
    _start_dt, end_dt = effective_interval(assignment)
    return now < end_dt


def _check_in_context(assignment, now, user):
    if assignment is None:
        return None
    settle_check_in(assignment, now, save=False)
    if assignment.checked_in_at:
        return {"assignment": assignment, "state": "checked", "hint": ""}
    if not can_check_in(user):
        return None
    if assignment.checked_out_at:
        return {
            "assignment": assignment,
            "state": "spent",
            "hint": _("You cannot check in again on this shift."),
        }
    state = check_in_state(assignment, now)
    hint = ""
    if state == "early":
        hint = _("You can check in from 30 minutes before this shift starts.")
    elif state == "closed":
        hint = _("This shift has ended.")
    return {"assignment": assignment, "state": state, "hint": hint}


def _check_in_sig(check_ins):
    """Which panels show and in what state. My shifts reloads nearby rows when it changes."""
    return ",".join(f"{item['assignment'].pk}:{item['state']}" for item in check_ins)


def _open_check_ins(user, now):
    if not has_own_shifts(user):
        return []
    today = timezone.localdate()
    rows = list(
        ShiftAssignment.objects.filter(
            user=user,
            date__in=[today - timedelta(days=1), today, today + timedelta(days=1)],
        ).select_related("shift_type", "user")
    )
    rows.sort(key=lambda row: (effective_interval(row)[0], row.pk))
    panels = []
    for row in rows:
        _start_dt, end_dt = effective_interval(row)
        if now >= end_dt:
            continue
        context = _check_in_context(row, now, user)
        if context and context["state"] in ("open", "checked", "spent"):
            panels.append(context)
    return panels


def _persist_ended_check_ins(user, now):
    """Write the auto check-out for this user's check-ins whose shift has ended."""
    rows = ShiftAssignment.objects.filter(user=user, checked_in_at__isnull=False).select_related("shift_type")
    for row in rows:
        settle_check_in(row, now)


@login_required
@require_POST
def shifts_check_in(request, pk):
    assignment = get_object_or_404(
        ShiftAssignment.objects.select_related("shift_type", "user"),
        pk=pk,
    )
    if assignment.user_id != request.user.id:
        return _forbid()
    if request.user.user_type != "support":
        return _forbid()
    # Page loads settle ended check-ins in memory only; this POST persists them.
    _persist_ended_check_ins(request.user, timezone.now())
    assignment.refresh_from_db(fields=["checked_in_at", "checked_out_at", "updated_at"])
    today = timezone.localdate()
    if assignment.date not in (today - timedelta(days=1), today, today + timedelta(days=1)):
        return _forbid()
    if not can_check_in(request.user):
        return _forbid()
    now = timezone.now()
    state = check_in_state(assignment, now)
    if assignment.date != today and state != "open":
        return _forbid()
    settle_check_in(assignment, now)
    if assignment.checked_out_at and not assignment.checked_in_at:
        return render(request, "shifts/check_in_panel.html", {
            "assignment": assignment,
            "state": "spent",
            "hint": _("You cannot check in again on this shift."),
        })
    if assignment.checked_in_at:
        return render(request, "shifts/check_in_panel.html", {"assignment": assignment, "state": "checked"})
    state = check_in_state(assignment, now)
    if state == "early":
        return render(request, "shifts/check_in_panel.html", {
            "assignment": assignment,
            "state": "early",
            "hint": _("You can check in from 30 minutes before this shift starts."),
        })
    if state == "closed":
        return render(request, "shifts/check_in_panel.html", {
            "assignment": assignment,
            "state": "closed",
            "hint": _("This shift has ended."),
        })
    assignment.checked_in_at = now
    assignment.checked_out_at = None
    assignment.arrived_at = assignment.arrived_at or now
    assignment.save(update_fields=["checked_in_at", "checked_out_at", "arrived_at", "updated_at"])
    if request.headers.get("HX-Request"):
        # Swap the whole list so every panel and the "on shift until" line agree.
        response = _check_ins_partial(request)
        response["HX-Retarget"] = "#shifts-check-in"
        response["HX-Reswap"] = "outerHTML"
        return response
    return render(request, "shifts/check_in_panel.html", {"assignment": assignment, "state": "checked"})

