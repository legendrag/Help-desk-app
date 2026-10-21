import logging
from datetime import date, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Max, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import time_format
from django.utils.translation import get_language, gettext as _
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.http_cache import apply_read_etag, etag_digest, htmx_not_modified, htmx_revalidation_match
from core.models import Department
from notifications.services import ShiftChange, queue_shift_changes
from shifts.clock import format_clock
from shifts.access import (
    can_check_in,
    display_name,
    has_own_shifts,
    home_target,
    is_shift_manager,
    shift_managers,
)
from shifts.availability import timeline_rows, timeline_window
from shifts.forms import ShiftTypeForm
from shifts.models import ShiftAssignment, ShiftType
from shifts.reports import build_report, report_filename, report_workbook
from shifts.services import (
    CHECKED_IN,
    COMPLETED,
    MISSED,
    NOT_CHECKED_IN,
    ON_SHIFT,
    BULK_MAX_DAYS,
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
    is_weekend,
    month_dates,
    neighbor_conflict,
    next_check_in_change,
    normalize_start,
    overlap_message,
    overrides_set_by_worker,
    plan_bulk,
    plan_copy,
    saturday_of,
    shift_outcome,
    week_dates,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _forbid():
    # Raised rather than returned so Django renders templates/403.html (a styled
    # page) instead of a bare line of text. Callers keep `return _forbid()`.
    raise PermissionDenied(_("You cannot open this page."))


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


def _rota_nav(view, start, dates, today):
    """Previous, Next and the Week link's start for the rota toolbars.

    Month → Week opens this week when it is in the month, else the month's first week.
    """
    prev_start, next_start = _step_start(view, start)
    week_start = saturday_of(today if view == "month" and dates[0] <= today <= dates[-1] else start)
    return {"prev_start": prev_start, "next_start": next_start, "week_start": week_start}


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
    now = timezone.now()
    today = timezone.localdate()
    check_ins = _open_check_ins(request.user, now)
    my_assignments = [a for a in bundle["assignments"] if a.user_id == request.user.id]
    refresh_in = next_check_in_change(my_assignments, now) if can_check_in(request.user) else None
    context = {
        **bundle,
        "department": department,
        "departments": Department.objects.order_by("name"),
        "view": view,
        "start": start,
        **_rota_nav(view, start, dates, today),
        "readonly": False,
        "shell_etag": etag,
        "now": now,
        "today": today,
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
    return _grid_response(request, _selected_department(request), retarget=False)


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
        "grid_etag": etag,
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



TIMELINE_TICK_STEP_HOURS = 3


def _timeline_ticks(day_start, day_length):
    """Hour labels every three hours from the window start; the closing 6 AM edge gets none."""
    ticks = []
    steps = int(day_length // (TIMELINE_TICK_STEP_HOURS * 3600))
    for index in range(steps):
        moment = timezone.localtime(day_start + timedelta(hours=index * TIMELINE_TICK_STEP_HOURS))
        clock = moment.time().replace(second=0, microsecond=0)
        ticks.append({
            "label": format_clock(clock),
            "short": time_format(clock, "g A"),
            "left": _timeline_percent(moment, day_start, day_length),
            "major": index % 2 == 0,  # every six hours, for phones
            "edge": index == 0,
            "last": index == steps - 1,
        })
    return ticks


def _timeline_percent(moment, day_start, day_length):
    offset = (moment - day_start).total_seconds() / day_length
    return round(min(max(offset, 0.0), 1.0) * 100, 3)


def _available_board(request):
    """Today's shifts, one row per person, grouped by department.

    The day runs from 9 AM (earlier when a shift starts between 6 and 9) to
    6 AM next morning (see timeline_window). Shifts running past either edge
    are clipped there.
    """
    now = timezone.now()
    today, day_start, day_end = timeline_window(now)
    day_length = (day_end - day_start).total_seconds()
    people = {}
    for row, start_dt, end_dt, state in timeline_rows(now, today, day_start, day_end):
        left = _timeline_percent(start_dt, day_start, day_length)
        key = (row.shift_type.department_id, row.user_id)
        person = people.setdefault(key, {
            "name": display_name(row.user),
            "phone": (row.user.phone or "").strip(),
            "bars": [],
        })
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
                    card["department"].pk, person["name"], person["phone"], bar["state"],
                    bar["start"].isoformat(), bar["end"].isoformat(),
                    bar["shift_type"].name, bar["shift_type"].colour,
                ))
    timeline = {
        "day_start": day_start,
        "day_end": day_end,
        "now": _timeline_percent(now, day_start, day_length),
        "now_inside": day_start <= now < day_end,
        "now_label": format_clock(now),
        "time_zone": timezone.get_current_timezone_name(),
        "ticks": _timeline_ticks(day_start, day_length),
        # Grid lines, one per tick step, as a share of the window.
        "step": round(TIMELINE_TICK_STEP_HOURS * 3600 / day_length * 100, 4),
    }
    return cards, timeline, etag_digest(parts)


@login_required
@require_GET
def shifts_available(request):
    cards, timeline, etag = _available_board(request)
    context = _available_context(request, cards, timeline, etag)
    # Outside the board, so the 20-second refresh never redraws it.
    context["contacts"] = shift_managers()
    return _shell(request, "shifts/available.html", context)


@login_required
@require_GET
def shifts_available_board(request):
    cards, timeline, etag = _available_board(request)
    if htmx_revalidation_match(request, etag):
        request.ticket_list_304_defer_session_save = True
        return htmx_not_modified(etag)
    response = render(request, "shifts/available_board.html", _available_context(request, cards, timeline, etag))
    return apply_read_etag(response, etag, request)


@login_required
@require_GET
def shifts_available_department(request, pk):
    """Who's available, for the ticket chat popup: one department, now and later today.

    With ``?ticket=<id>`` the viewer gets a Transfer button per person when
    they may transfer that ticket (same rule as the chat's Transfer action).
    """
    from tickets.models import Ticket

    department = get_object_or_404(Department, pk=pk)
    now = timezone.now()
    day, window_start, window_end = timeline_window(now)
    on_now = {}
    late = {}  # on the clock now but not checked in, as on the Available now board
    later = {}
    for row, start_dt, end_dt, state in timeline_rows(now, day, window_start, window_end, department.pk):
        if row.user.status != User.Status.ACTIVE:
            continue
        if state == "on":
            current = on_now.get(row.user_id)
            if current is None or end_dt > current["end"]:
                on_now[row.user_id] = {"user": row.user, "shift_type": row.shift_type, "end": end_dt}
        elif state == "late":
            current = late.get(row.user_id)
            if current is None or end_dt > current["end"]:
                late[row.user_id] = {"user": row.user, "shift_type": row.shift_type, "end": end_dt}
        elif state == "later":
            current = later.get(row.user_id)
            if current is None or start_dt < current["start"]:
                later[row.user_id] = {"user": row.user, "shift_type": row.shift_type, "start": start_dt}
    # Each person once, in their best group: on now, then not checked in, then later.
    for user_id in on_now:
        late.pop(user_id, None)
        later.pop(user_id, None)
    for user_id in late:
        later.pop(user_id, None)
    for person in list(on_now.values()) + list(late.values()) + list(later.values()):
        person["name"] = display_name(person["user"])
        person["phone"] = (person["user"].phone or "").strip()
    ticket = None
    ticket_pk = _parse_pk(request.GET.get("ticket"))
    if ticket_pk is not None:
        ticket = Ticket.objects.filter(pk=ticket_pk).only(
            "id", "assigned_to_id", "pending_transfer_to_id", "department_id",
        ).first()
    viewer = request.user
    can_transfer = bool(
        ticket
        and ticket.department_id == department.pk
        and not ticket.pending_transfer_to_id
        and (viewer.is_superuser or ticket.assigned_to_id == viewer.pk)
    )
    # Not checked in is listed, not offered: Transfer stays for people on shift.
    for person in on_now.values():
        person["can_transfer"] = can_transfer and person["user"].pk != ticket.assigned_to_id
    return render(request, "shifts/available_popup.html", {
        "department": department,
        "on_now": sorted(on_now.values(), key=lambda person: person["name"].casefold()),
        "late": sorted(late.values(), key=lambda person: person["name"].casefold()),
        "later": sorted(later.values(), key=lambda person: (person["start"], person["name"].casefold())),
        "show_shift_type": _shows_shift_types(viewer),
    })


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
    department = _default_department(request.user)
    if department is None:
        raise Http404(_("No department exists."))
    return department


@login_required
@require_http_methods(["GET", "POST"])
def shifts_type_add(request):
    if not is_shift_manager(request.user):
        return _forbid()
    # The Add button passes the department being viewed; start the form on it.
    initial = {}
    department_pk = _parse_pk(request.GET.get("department"))
    if department_pk and Department.objects.filter(pk=department_pk).exists():
        initial["department"] = department_pk
    form = ShiftTypeForm(request.POST or None, initial=initial)
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
    old_times = (row.start_time, row.end_time)
    form = ShiftTypeForm(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        if (saved.start_time, saved.end_time) != old_times:
            # New times move every upcoming shift of this type that has no
            # times of its own; tell those people (past shifts are skipped).
            moved = (
                ShiftAssignment.objects.filter(
                    shift_type=saved,
                    date__gte=timezone.localdate() - timedelta(days=1),
                )
                .filter(Q(start_time_override__isnull=True) | Q(end_time_override__isnull=True))
                .select_related("user", "shift_type")
            )
            queue_shift_changes([ShiftChange.of("changed", a) for a in moved], request.user)
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
    if request.headers.get("HX-Request"):
        # The page posts its department, so the list stays on it.
        return _render_types(request)
    # Back to the department being viewed, not the default one.
    query = urlencode({"department": row.department_id})
    return redirect(f"{reverse('shifts_types')}?{query}")


def _department_with_shift_types():
    return (
        Department.objects.filter(shift_types__isnull=False)
        .distinct()
        .order_by("name")
        .first()
    )


def _default_department(user):
    """The department a Shifts page opens on when none is chosen: the user's own
    when it has shift types, else the first that has any, else the user's own,
    else the first by name."""
    own_id = getattr(user, "department_id", None)
    if own_id and ShiftType.objects.filter(department_id=own_id).exists():
        return user.department
    return (
        _department_with_shift_types()
        or (user.department if own_id else None)
        or Department.objects.order_by("name").first()
    )


def _render_types(request):
    department = _selected_department(request)
    rows = (
        ShiftType.objects.filter(department=department)
        .select_related("department")
        .order_by("archived", "name")
    )
    return _shell(request, "shifts/types.html", {
        "department": department,
        "types": rows,
        "departments": Department.objects.order_by("name"),
        # Also rendered after add/edit/archive posts, whose URL names differ.
        "active_tab": "shifts_types",
    })


@login_required
@require_GET
def shifts_types(request):
    if not is_shift_manager(request.user):
        return _forbid()
    return _render_types(request)


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
        or request.POST.get("remove") == "1"
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
    # The Remove button, or "Remove this shift" picked in the type list.
    shift_type_id = "" if request.POST.get("remove") == "1" else request.POST.get("shift_type") or ""
    if not shift_type_id:
        if existing:
            removed = ShiftChange.of("removed", existing)
            existing.delete()
            queue_shift_changes([removed], request.user)
        response = _grid_response(request, department, retarget=True)
        response["HX-Trigger"] = "closeModal"
        return response
    if _parse_pk(shift_type_id) is None:
        raise Http404(_("That shift no longer exists."))
    shift_type = get_object_or_404(ShiftType, pk=int(shift_type_id), department=department)
    if request.POST.get("reset_times") == "1" and existing:
        before = effective_interval(existing)
        existing.start_time_override = None
        existing.end_time_override = None
        existing.times_set_by = None
        existing.times_set_at = None
        existing.save()
        if effective_interval(existing) != before:
            queue_shift_changes([ShiftChange.of("changed", existing)], request.user)
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
    before = effective_interval(existing) if existing else None
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
    # Saving the dialog unchanged tells nobody anything.
    if existing is None:
        queue_shift_changes([ShiftChange.of("added", row)], request.user)
    elif type_changed or effective_interval(row) != before:
        queue_shift_changes([ShiftChange.of("changed", row)], request.user)
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
    rota_start = _parse_day(request.POST.get("start") or request.GET.get("start"))
    return render(request, "shifts/cell_form.html", {
        "department": department,
        "person": user,
        "on": on,
        "existing": existing,
        # The shift's own type stays listed even when archived, so the select
        # never silently falls back to another type.
        "types": ShiftType.objects.filter(department=department).filter(
            Q(archived=False) | Q(pk=getattr(existing, "shift_type_id", None))
        ),
        "can_restore": _can_restore_check_in(existing, now),
        "error": error,
        "selected_type": selected_type,
        "start_value": start_value,
        "end_value": end_value,
        "rota_view": request.POST.get("view") or request.GET.get("view") or "",
        "rota_start": rota_start.isoformat() if rota_start else "",
    })


def _write_planned(planned, changes=None):
    """Create the planned rows; each new one is added to ``changes`` when given."""
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
        row = ShiftAssignment.objects.create(
            user_id=item["user_id"],
            date=item["date"],
            shift_type=shift_type,
            start_time_override=item["start"],
            end_time_override=item["end"],
            times_set_by_id=item["times_set_by_id"],
            times_set_at=item["times_set_at"],
            checked_in_at=None,
        )
        if changes is not None:
            changes.append(ShiftChange.of("added", row))
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
    changes = []
    with transaction.atomic():
        created, skips = _write_planned(plan_copy(source_rows, timedelta(days=7), request.user), changes)
        queue_shift_changes(changes, request.user)
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
    changes = []  # every week together: one summary per person
    with transaction.atomic():
        for k in range(1, weeks + 1):
            made, skipped = _write_planned(plan_copy(source_rows, timedelta(days=7 * k), request.user), changes)
            created += made
            skips.extend(skipped)
            source_rows = list(
                ShiftAssignment.objects.filter(
                    shift_type__department=department,
                    date__gte=start,
                    date__lte=start + timedelta(days=6),
                ).select_related("shift_type", "times_set_by", "times_set_by__role")
            )
        queue_shift_changes(changes, request.user)
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


def _apply_rotation(proposals, shift_type, department, changes=None, per_day=None):
    """Create the planned rows. ``per_day`` caps people per day on this shift,
    counted again here, so a stale preview can't overfill a day."""
    for attempt in range(3):
        made = []
        # Fresh copies per try: a failed try must not leave half-set skips.
        items = [dict(item) for item in proposals]
        try:
            created, skips = _apply_rotation_once(items, shift_type, department, made, per_day)
        except (OperationalError, IntegrityError):
            # A database deadlock or clash with another save: try again.
            logger.warning("Rota apply clashed with another save (attempt %s)", attempt + 1, exc_info=True)
            continue
        if changes is not None:
            changes.extend(made)
        for original, item in zip(proposals, items):
            original.update(item)  # callers read the names set here
        return created, skips
    return 0, [
        dict(item, skip=_("Someone else changed the rota at the same time. Preview again."))
        for item in proposals if not item.get("gap")
    ]


def _apply_rotation_once(proposals, shift_type, department, made, per_day):
    created = 0
    skips = []
    with transaction.atomic():
        # One Apply per department at a time: a second one waits here, then
        # sees the first one's rows (no duplicates, no deadlock between them).
        Department.objects.select_for_update().filter(pk=department.pk).first()
        taken = {}
        if per_day is not None:
            for day in ShiftAssignment.objects.filter(
                shift_type=shift_type, date__in={item["date"] for item in proposals if not item.get("gap")},
            ).values_list("date", flat=True):
                taken[day] = taken.get(day, 0) + 1
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
            if shift_type.archived or shift_type.department_id != department.pk:
                item["skip"] = _("Archived shift types cannot be assigned.")
                skips.append(item)
                continue
            if ShiftAssignment.objects.filter(
                user_id=user.pk, date=item["date"], shift_type=shift_type
            ).exists():
                item["skip"] = _("already has this shift")
                skips.append(item)
                continue
            if per_day is not None and taken.get(item["date"], 0) >= per_day:
                # Someone else filled the day after the preview.
                item["skip"] = _("this day already has enough people on this shift")
                skips.append(item)
                continue
            probe = ShiftAssignment(user=user, date=item["date"], shift_type=shift_type)
            start_dt, end_dt = interval_for(item["date"], shift_type.start_time, shift_type.end_time)
            other = neighbor_conflict(probe, start_dt, end_dt)
            if other:
                item["skip"] = overlap_message(other)
                skips.append(item)
                continue
            row = ShiftAssignment.objects.create(
                user=user,
                shift_type=shift_type,
                date=item["date"],
                start_time_override=None,
                end_time_override=None,
                times_set_by=None,
                times_set_at=None,
                checked_in_at=None,
            )
            made.append(ShiftChange.of("added", row))
            taken[item["date"]] = taken.get(item["date"], 0) + 1
            created += 1
    return created, skips


def _rotation_choices(department):
    if department is None:
        return [], []
    bulk_types = list(
        ShiftType.objects.filter(department=department, archived=False).order_by("-is_night", "start_time", "name")
    )
    people = list(User.objects.filter(
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ).order_by("first_name", "last_name", "username"))
    for person in people:
        person.shift_label = display_name(person)
    return bulk_types, people


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


def _posted_bulk_type(request, department):
    raw = (request.POST.get("shift_type") or "").strip()
    if not raw.isdigit():
        raise Http404(_("Archived shift types cannot be assigned."))
    return get_object_or_404(ShiftType, pk=int(raw), department=department, archived=False)


def _posted_dates(request):
    try:
        start = date.fromisoformat(request.POST.get("start") or "")
        end = date.fromisoformat(request.POST.get("end") or "")
    except ValueError:
        return None, None
    return start, end


def _bulk_weekdays():
    """(weekday number, name) for the Skip weekdays chips, Saturday first like the rota."""
    from shifts.templatetags.shifts_extras import shifts_weekday

    first = saturday_of(timezone.localdate())
    return [((first + timedelta(days=i)).weekday(), shifts_weekday(first + timedelta(days=i))) for i in range(7)]


def _hours_text(minutes):
    hours = round(minutes / 60, 1)
    return f"{hours:g}"


def _bulk_existing(people, first, last):
    """Each person's shifts around the run: the fair-share lookback, the run,
    and a day either side for nights in a row and overlaps."""
    from shifts.services import NIGHT_ROTATION_LOOKBACK_DAYS

    by_user = {person.pk: [] for person in people}
    rows = ShiftAssignment.objects.filter(
        user__in=people,
        date__gte=first - timedelta(days=NIGHT_ROTATION_LOOKBACK_DAYS + 1),
        date__lte=last + timedelta(days=1),
    ).select_related("shift_type", "user")
    for row in rows:
        by_user.setdefault(row.user_id, []).append(row)
    return by_user


def _bulk_grid(people, dates, day_notes, shift_type, plan, gaps, added=()):
    """The preview as a small rota: a row per person, a column per day."""
    existing = {}
    rows = ShiftAssignment.objects.filter(user__in=people, date__in=dates).select_related("shift_type")
    for row in rows:
        existing.setdefault((row.user_id, row.date), []).append(row)
    for cell_rows in existing.values():
        cell_rows.sort(key=lambda row: (effective_interval(row)[0], row.pk))
    proposed = {(item["user_id"], item["date"]): item for item in plan}
    missing = {gap["date"]: gap["missing"] for gap in gaps}
    today = timezone.localdate()
    shift_minutes = clock_length(shift_type.start_time, shift_type.end_time)[0]
    columns = [
        {
            "day": day,
            "skip": day_notes.get(day, ""),
            "missing": missing.get(day, 0),
            "weekend": is_weekend(day),
            "today": day == today,
        }
        for day in dates
    ]
    grid = []
    for person in people:
        cells = []
        total = new = weekend = minutes = 0
        for column in columns:
            day = column["day"]
            mine = existing.get((person.pk, day), [])
            item = proposed.get((person.pk, day))
            for row in mine:
                row.just_added = (person.pk, day) in added and row.shift_type_id == shift_type.pk
                if row.shift_type_id == shift_type.pk:
                    total += 1
                    weekend += column["weekend"]
                    minutes += clock_length(*effective_times(row))[0]
            if item:
                total += 1
                new += 1
                weekend += column["weekend"]
                minutes += shift_minutes
            cells.append({"column": column, "rows": mine, "proposed": item})
        grid.append({
            "person": person,
            "name": display_name(person),
            "cells": cells,
            "total": total,
            "new": new,
            "weekend": weekend,
            "hours": _hours_text(minutes),
        })
    return columns, grid


def _bulk_form(request, people):
    """Every field of the card, so Apply resends exactly what was previewed."""
    keys = ("department", "shift_type", "start", "end", "mode", "per_day")
    fields = [(key, request.POST.get(key, "")) for key in keys]
    fields += [("skip_weekday", value) for value in request.POST.getlist("skip_weekday")]
    fields += [("skip_date", value) for value in request.POST.getlist("skip_date") if value]
    fields += [("users", person.pk) for person in people]
    return fields


@login_required
@require_POST
def shifts_calc_rotation(request):
    """Calculator → Bulk assign: preview a shift for the ticked people over a
    date range, shared fairly or given to everyone, then apply exactly that."""
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    if not (request.POST.get("shift_type") or "").strip():
        # A department with no shift types posts nothing (the list is disabled).
        return render(request, "shifts/calc_bulk.html", {
            "error": _("Add a shift type to this department first, under Shift types."),
        })
    shift_type = _posted_bulk_type(request, department)
    start, end = _posted_dates(request)
    context = {"department": department, "shift_type": shift_type}
    if start is None or end is None:
        return render(request, "shifts/calc_bulk.html", {**context, "error": _("Enter a start and an end date.")})
    dates = _dates_inclusive(start, end)
    if len(dates) > BULK_MAX_DAYS:
        return render(request, "shifts/calc_bulk.html", {
            **context, "error": _("Choose at most %(days)s days.") % {"days": BULK_MAX_DAYS},
        })
    people = list(User.objects.filter(
        pk__in=[pk for pk in map(_parse_pk, request.POST.getlist("users")) if pk is not None],
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ).order_by("first_name", "last_name", "username"))
    if not people:
        return render(request, "shifts/calc_bulk.html", {**context, "error": _("Tick at least one person.")})

    everyone = request.POST.get("mode") == "everyone"
    try:
        per_day = int(request.POST.get("per_day") or 1)
    except ValueError:
        per_day = 1
    per_day = min(max(per_day, 1), len(people))
    skip_weekdays = {
        int(value) for value in request.POST.getlist("skip_weekday") if value.isdigit() and int(value) < 7
    }
    skip_dates = set()
    for value in request.POST.getlist("skip_date"):
        try:
            skip_dates.add(date.fromisoformat(value))
        except ValueError:
            continue
    today = timezone.localdate()
    day_notes = {}
    for day in dates:
        if day < today:
            day_notes[day] = _("Past")
        elif day in skip_dates:
            day_notes[day] = _("Skipped date")
        elif day.weekday() in skip_weekdays:
            day_notes[day] = _("Skipped day")
    open_dates = [day for day in dates if day not in day_notes]

    covered = {}
    for day in ShiftAssignment.objects.filter(shift_type=shift_type, date__in=open_dates).values_list("date", flat=True):
        covered[day] = covered.get(day, 0) + 1
    plan, gaps = plan_bulk(
        people, open_dates, shift_type, _bulk_existing(people, dates[0], dates[-1]),
        per_day=per_day, everyone=everyone, covered=covered,
    )

    created, skips, added = 0, [], set()
    if request.POST.get("action") == "apply":
        posted = request.POST.getlist("plan")
        if posted:
            # Apply what the preview showed, still checked row by row below.
            allowed = {person.pk for person in people}
            open_set = set(open_dates)
            plan = []
            for value in posted:
                user_raw, _sep, day_raw = value.partition(":")
                try:
                    item = {"user_id": int(user_raw), "date": date.fromisoformat(day_raw)}
                except ValueError:
                    continue
                if item["user_id"] in allowed and item["date"] in open_set:
                    plan.append(item)
        changes = []
        created, skips = _apply_rotation(
            [dict(item) for item in plan], shift_type, department, changes, per_day=None if everyone else per_day,
        )
        queue_shift_changes(changes, request.user)
        skipped_keys = {(item["user_id"], item["date"]) for item in skips}
        added = {(item["user_id"], item["date"]) for item in plan} - skipped_keys
        _attach_names(skips, people)
        plan = []

    columns, grid = _bulk_grid(people, dates, day_notes, shift_type, plan, gaps, added)
    response = render(request, "shifts/calc_bulk.html", {
        **context,
        "columns": columns,
        "grid": grid,
        "plan": plan,
        "gaps": gaps,
        "skips": skips,
        "created": created,
        "applied": request.POST.get("action") == "apply",
        "everyone": everyone,
        "per_day": per_day,
        "back_to_back": sum(1 for item in plan if item.get("back_to_back")),
        "form_fields": _bulk_form(request, people),
        "month_view": len(dates) > 7,
    })
    if created:
        response["HX-Trigger"] = "shiftsChanged"
    return response


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
            "view": view,
            "start": start,
            "readonly": False,
            "today": timezone.localdate(),
            "now": timezone.now(),
            "grid_oob": True,
        })
    return render(request, "shifts/action_result.html", context)


def _hours_minutes(minutes):
    return minutes // 60, minutes % 60


@login_required
@require_GET
def shifts_calculator(request):
    if not is_shift_manager(request.user):
        return _forbid()
    raw = request.GET.get("department")
    department = _department_or_404(raw) if raw else _default_department(request.user)
    bulk_types, people = _rotation_choices(department)
    context = {
        "departments": Department.objects.order_by("name"),
        "department": department,
        "bulk_types": bulk_types,
        "people": people,
        "bulk_weekdays": _bulk_weekdays(),
    }
    if request.GET.get("part") == "rotation":
        return render(request, "shifts/calculator_rotation_options.html", context)
    context["work_people"] = _work_hours_people(department)
    context["work_shift_types"] = _work_hours_shift_types(department)
    context["work_has_night"] = any(shift_type.is_night for shift_type in context["work_shift_types"])
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


def _work_hours_shift_types(department):
    """The department's shift types for the work hours Shifts switches."""
    if department is None:
        return []
    return list(ShiftType.objects.filter(department=department, archived=False).order_by("start_time", "name"))


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
    # "Night shifts only" wins; otherwise the ticked shift types, none = all.
    night_only = request.GET.get("shifts") == "night"
    shift_types = []
    if not night_only:
        picked = {pk for pk in map(_parse_pk, request.GET.getlist("shift_type")) if pk is not None}
        department_pk = _parse_pk(request.GET.get("department")) or (person.department_id if person else None)
        if picked and department_pk:
            # Only the department's active types, the ones the switches list.
            offered = _work_hours_shift_types(Department.objects.filter(pk=department_pk).first())
            shift_types = [shift_type for shift_type in offered if shift_type.pk in picked]
            if len(shift_types) == len(offered):
                shift_types = []  # every type ticked is all shifts, as on the page
    return person, start, end, night_only, shift_types


@login_required
@require_GET
def shifts_calc_work(request):
    """One person's shifts in a date range, laid out like the paper statement."""
    if not is_shift_manager(request.user):
        return _forbid()
    person, start, end, night_only, shift_types = _work_hours_request(request)
    if person is None:
        return render(request, "shifts/calc_work.html", {"error": _("Choose a person.")})
    report = build_report(person, start, end, night_only, shift_types=shift_types)
    # The filter exactly as the report applied it: night, the picked types, or all.
    department_pk = _parse_pk(request.GET.get("department"))
    export_query = urlencode([
        ("person", person.pk),
        ("start", report.start.isoformat()),
        ("end", report.end.isoformat()),
        *([("department", department_pk)] if department_pk else []),
        *([] if shift_types else [("shifts", "night" if night_only else "all")]),
        *(("shift_type", shift_type.pk) for shift_type in shift_types),
    ])
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
    person, start, end, night_only, shift_types = _work_hours_request(request)
    if person is None:
        raise Http404(_("Choose a person."))
    report = build_report(person, start, end, night_only, shift_types=shift_types)
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
        department = _selected_department(request)
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
    today = timezone.localdate()
    return _shell(request, "shifts/team.html", {
        **bundle,
        "department": department,
        "departments": Department.objects.order_by("name"),
        "view": view,
        "start": start,
        **_rota_nav(view, start, dates, today),
        "readonly": True,
        "today": today,
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

