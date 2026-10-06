from datetime import date, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language, gettext as _
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.http_cache import apply_read_etag, etag_digest, htmx_not_modified, htmx_revalidation_match
from core.models import Department
from shifts.access import display_name, home_target, is_shift_manager
from shifts.forms import ShiftTypeForm
from shifts.models import ShiftAssignment, ShiftType
from shifts.services import (
    REPEAT_WEEKS_MAX,
    WORKER_HOURS_LOOKBACK_DAYS,
    WORKER_HOURS_MAX_MINUTES,
    aware_on,
    clipped_day_night_minutes,
    clock_length,
    check_in_marker,
    check_in_state,
    effective_interval,
    effective_times,
    interval_for,
    month_dates,
    neighbor_conflict,
    normalize_start,
    overlap_message,
    overrides_set_by_worker,
    plan_copy,
    suggest_nights,
    week_dates,
)

User = get_user_model()


def _forbid():
    return HttpResponseForbidden(_("You cannot open this page."))


def _shell(request, template, context):
    context["is_manager"] = is_shift_manager(request.user)
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
    raw = request.POST.get("start") or request.GET.get("start")
    day = date.fromisoformat(raw) if raw else timezone.localdate()
    start = normalize_start(day, view)
    dates = month_dates(start) if view == "month" else week_dates(start)
    return view, start, dates


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
        ).select_related("user", "shift_type", "times_set_by", "times_set_by__role")
    )
    visible = [row for row in assignments if first <= row.date <= last]
    now = timezone.now()
    for row in visible:
        row.set_by_worker = overrides_set_by_worker(row)
        row.check_marker = check_in_marker(row, now)
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
    by_key = {(row.user_id, row.date): row for row in visible}
    for person in ordered:
        person.shift_label = display_name(person)
        person.cells = [(day, by_key.get((person.pk, day))) for day in dates]
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
    ])


def _grid_response(request, department, retarget=False, notice="", skips=None, error=""):
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    etag = _rota_etag(department, view, start, bundle["assignments"])
    if not retarget and htmx_revalidation_match(request, etag):
        return htmx_not_modified(etag)
    prev_start, next_start = _step_start(view, start)
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
        "now": timezone.now(),
        "today": timezone.localdate(),
        "notice": notice,
        "skips": skips or [],
        "error": error,
        "display_name": display_name,
        "check_in": _viewer_check_in(request),
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
        "readonly": False,
        "today": timezone.localdate(),
        "now": timezone.now(),
    })
    return apply_read_etag(response, etag, request)


@login_required
@require_GET
def shifts_mine(request):
    if request.user.user_type != "support" and not is_shift_manager(request.user):
        return _forbid()
    today = timezone.localdate()
    lookback = today - timedelta(days=WORKER_HOURS_LOOKBACK_DAYS)
    upcoming = list(
        ShiftAssignment.objects.filter(user=request.user, date__gte=today).select_related("shift_type")
    )
    past_nights = list(
        ShiftAssignment.objects.filter(
            user=request.user,
            shift_type__is_night=True,
            date__gte=lookback,
            date__lt=today,
        ).select_related("shift_type")
    )
    rows = sorted(upcoming + past_nights, key=lambda row: (row.date, row.pk))
    now = timezone.now()
    banner_end = None
    for row in rows:
        start_dt, end_dt = effective_interval(row)
        if start_dt <= now < end_dt:
            banner_end = end_dt
            break
    check_in = None
    if request.user.user_type == "support":
        check_in = next((row for row in rows if row.date == today and not row.shift_type.is_night), None)
    return _shell(request, "shifts/mine.html", {
        "assignments": rows,
        "banner_end": banner_end,
        "today": today,
        "check_in": _check_in_context(check_in, now),
    })


def _available_board(request):
    now = timezone.now()
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    rows = list(
        ShiftAssignment.objects.filter(date__in=[yesterday, today])
        .select_related("user", "shift_type", "shift_type__department")
    )
    checked = [row.checked_in_at for row in rows if row.checked_in_at]
    on_shift = []
    for row in rows:
        start_dt, end_dt = effective_interval(row)
        if not (start_dt <= now < end_dt):
            continue
        if row.shift_type.is_night or row.checked_in_at:
            on_shift.append((row, end_dt))
    parts = [
        get_language(),
        max(checked).isoformat() if checked else "",
        len(checked),
    ]
    by_department = {}
    for row, end_dt in on_shift:
        by_department.setdefault(row.shift_type.department_id, []).append((row, end_dt))
    for department_id in sorted(by_department):
        tuples = []
        for row, end_dt in by_department[department_id]:
            start_dt, real_end = effective_interval(row)
            tuples.append((
                row.user_id,
                start_dt.isoformat(),
                real_end.isoformat(),
                row.times_set_at.isoformat() if row.times_set_at else "",
                row.checked_in_at.isoformat() if row.checked_in_at else "",
            ))
        parts.append((department_id, tuple(sorted(tuples))))
    etag = etag_digest(parts)
    cards = []
    for department in Department.objects.order_by("name"):
        people = []
        for row, end_dt in sorted(by_department.get(department.pk, []), key=lambda item: item[0].user_id):
            people.append({"name": display_name(row.user), "end": end_dt})
        cards.append({"department": department, "people": people})
    return cards, etag


@login_required
@require_GET
def shifts_available(request):
    cards, etag = _available_board(request)
    return _shell(request, "shifts/available.html", {"cards": cards, "board_etag": etag})


@login_required
@require_GET
def shifts_available_board(request):
    cards, etag = _available_board(request)
    if htmx_revalidation_match(request, etag):
        request.ticket_list_304_defer_session_save = True
        return htmx_not_modified(etag)
    response = render(request, "shifts/available_board.html", {"cards": cards, "board_etag": etag})
    return apply_read_etag(response, etag, request)


def _selected_department(request):
    raw = request.POST.get("department") or request.GET.get("department")
    if raw:
        return get_object_or_404(Department, pk=raw)
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
        form.save()
        return _render_types(request)
    return render(request, "shifts/type_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def shifts_type_edit(request, pk):
    if not is_shift_manager(request.user):
        return _forbid()
    row = get_object_or_404(ShiftType, pk=pk)
    form = ShiftTypeForm(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        form.save()
        return _render_types(request)
    return render(request, "shifts/type_form.html", {"form": form, "editing": True})


@login_required
@require_POST
def shifts_type_archive(request, pk):
    if not is_shift_manager(request.user):
        return _forbid()
    row = get_object_or_404(ShiftType, pk=pk)
    row.archived = True
    row.save()
    return redirect("shifts_types")


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
    })


@login_required
@require_GET
def shifts_types(request):
    if not is_shift_manager(request.user):
        return _forbid()
    return _render_types(request)


def _parse_clock(raw):
    if not raw:
        return None
    return time.fromisoformat(raw)


@login_required
@require_http_methods(["GET", "POST"])
def shifts_cell(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    user = get_object_or_404(User, pk=request.POST.get("user") or request.GET.get("user"))
    on = date.fromisoformat(request.POST.get("date") or request.GET.get("date"))
    existing = (
        ShiftAssignment.objects.filter(user=user, date=on)
        .select_related("shift_type")
        .first()
    )
    if request.method == "GET":
        return render(request, "shifts/cell_form.html", {
            "department": department,
            "person": user,
            "on": on,
            "existing": existing,
            "types": ShiftType.objects.filter(department=department, archived=False),
        })
    if request.method == "POST" and request.POST.get("clear_check_in") == "1":
        if existing and not existing.shift_type.is_night:
            existing.checked_in_at = None
            existing.save(update_fields=["checked_in_at", "updated_at"])
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
    shift_type = get_object_or_404(ShiftType, pk=shift_type_id, department=department)
    if request.POST.get("reset_times") == "1" and existing:
        existing.start_time_override = None
        existing.end_time_override = None
        existing.times_set_by = None
        existing.times_set_at = None
        existing.save()
        response = _grid_response(request, department, retarget=True)
        response["HX-Trigger"] = "closeModal"
        return response
    start_t = _parse_clock(request.POST.get("start_time_override"))
    end_t = _parse_clock(request.POST.get("end_time_override"))
    error = None
    if (start_t is None) ^ (end_t is None):
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
    if error:
        return render(request, "shifts/cell_form.html", {
            "department": department,
            "person": user,
            "on": on,
            "existing": existing,
            "types": ShiftType.objects.filter(department=department, archived=False),
            "error": error,
        })
    row = existing or ShiftAssignment(user=user, date=on)
    was_day = bool(existing and not existing.shift_type.is_night)
    row.shift_type = shift_type
    if start_t is not None and end_t is not None:
        row.start_time_override = start_t
        row.end_time_override = end_t
        row.times_set_by = request.user
        row.times_set_at = timezone.now()
    if was_day and shift_type.is_night:
        row.checked_in_at = None
    row.save()
    response = _grid_response(request, department, retarget=True)
    response["HX-Trigger"] = "closeModal"
    return response


def _write_planned(planned):
    created = 0
    skips = []
    for item in sorted(planned, key=lambda row: row["date"]):
        if item["skip"]:
            skips.append(item)
            continue
        if ShiftAssignment.objects.filter(user_id=item["user_id"], date=item["date"]).exists():
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
    start = normalize_start(date.fromisoformat(request.POST["start"]), "week")
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
    return _grid_response(request, department, retarget=False, notice=notice, skips=skips)


@login_required
@require_POST
def shifts_repeat_week(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    start = normalize_start(date.fromisoformat(request.POST["start"]), "week")
    try:
        weeks = int(request.POST.get("weeks") or "")
    except ValueError:
        weeks = 0
    if weeks < 1 or weeks > REPEAT_WEEKS_MAX:
        return _grid_response(
            request,
            department,
            retarget=False,
            error=_("Enter a number of weeks from 1 to 12."),
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
    return _grid_response(request, department, retarget=False, notice=notice, skips=skips)


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
            if ShiftAssignment.objects.filter(user_id=user.pk, date=item["date"]).exists():
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
            "error": _("Enter both a start and an end time."),
        })
    dates = _dates_inclusive(start, end)
    people = list(User.objects.filter(
        pk__in=request.POST.getlist("users"),
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
                if ShiftAssignment.objects.filter(user=person, date=day).exists():
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


def _rota_redirect(request, department, view, start, message):
    messages.success(request, message)
    query = urlencode({
        "department": department.pk,
        "view": view,
        "start": start.isoformat(),
    })
    return redirect(f"{reverse('shifts_rota')}?{query}")


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
        notice = _("This department has no night shift.")
        if not htmx:
            return _rota_redirect(request, department, view, start, notice)
        return _grid_response(request, department, notice=notice)
    chosen_id = (request.POST.get("shift_type") or "").strip()
    shift_type = night_types[0]
    if chosen_id:
        shift_type = _posted_night_type(request, department)
    elif len(night_types) > 1:
        if not htmx:
            return _rota_redirect(request, department, view, start, _("Choose a night shift type on the rota."))
        return render(request, "shifts/calc_rotation.html", {
            "pick_types": night_types,
            "department": department,
            "proposals": [],
            "skips": [],
            "created": 0,
        })
    people = list(User.objects.filter(
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ))
    proposals = suggest_nights(people, dates, shift_type, _people_and_existing(people))
    _attach_names(proposals, people)
    if request.POST.get("action") != "apply":
        if not htmx:
            return _rota_redirect(request, department, view, start, _("Open the rota to review the night rotation."))
        return render(request, "shifts/calc_rotation.html", {
            "proposals": proposals,
            "skips": [],
            "created": 0,
            "department": department,
            "shift_type": shift_type,
            "can_apply": True,
        })
    created, skips = _apply_rotation(proposals, shift_type, department)
    _attach_names(skips, people)
    notice = _("Filled %(count)s night shifts.") % {"count": created}
    if not htmx:
        return _rota_redirect(request, department, view, start, notice)
    return _grid_response(request, department, retarget=True, notice=notice, skips=skips)


def _hours_minutes(minutes):
    return minutes // 60, minutes % 60


def _format_minutes(minutes):
    hours, mins = _hours_minutes(minutes)
    return _("%(hours)s hours %(minutes)s minutes") % {"hours": hours, "minutes": mins}


@login_required
@require_GET
def shifts_calculator(request):
    if not is_shift_manager(request.user):
        return _forbid()
    raw = request.GET.get("department")
    if raw:
        department = get_object_or_404(Department, pk=raw)
    else:
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
    return _shell(request, "shifts/calculator.html", context)


@login_required
@require_GET
def shifts_calc_length(request):
    if not is_shift_manager(request.user):
        return _forbid()
    try:
        start_t = time.fromisoformat(request.GET.get("start", ""))
        end_t = time.fromisoformat(request.GET.get("end", ""))
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
@require_GET
def shifts_calc_hours(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    range_start = aware_on(dates[0], time(0, 0))
    range_end = aware_on(dates[-1] + timedelta(days=1), time(0, 0))
    totals = {}
    for row in bundle["assignments"]:
        day_m, night_m = clipped_day_night_minutes(row, range_start, range_end)
        bucket = totals.setdefault(row.user_id, {"user": row.user, "day": 0, "night": 0})
        bucket["day"] += day_m
        bucket["night"] += night_m
    people = []
    for bucket in totals.values():
        if bucket["day"] == 0 and bucket["night"] == 0:
            continue
        people.append({
            "name": display_name(bucket["user"]),
            "day": _format_minutes(bucket["day"]),
            "night": _format_minutes(bucket["night"]),
            "total": _format_minutes(bucket["day"] + bucket["night"]),
        })
    return render(request, "shifts/calc_hours.html", {
        "people": people,
        "department": department,
        "view": view,
        "start": start,
    })


@login_required
@require_GET
def shifts_calc_coverage(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    intervals = [effective_interval(row) for row in bundle["assignments"]]
    rows = []
    for hour in range(24):
        cells = []
        for day in dates:
            bucket_start = aware_on(day, time(hour, 0))
            bucket_end = bucket_start + timedelta(hours=1)
            count = 0
            for start_dt, end_dt in intervals:
                if start_dt < bucket_end and bucket_start < end_dt:
                    count += 1
            cells.append({"day": day, "hour": hour, "count": count})
        rows.append({"hour": hour, "cells": cells})
    return render(request, "shifts/calc_coverage.html", {
        "rows": rows,
        "dates": dates,
        "department": department,
        "view": view,
        "start": start,
    })


@login_required
@require_POST
def shifts_mine_hours(request, pk):
    assignment = get_object_or_404(
        ShiftAssignment.objects.select_related("shift_type", "user"),
        pk=pk,
    )
    if assignment.user_id != request.user.id:
        return _forbid()
    if not assignment.shift_type.is_night:
        return _forbid()
    if request.user.user_type != "support" and not is_shift_manager(request.user):
        return _forbid()
    today = timezone.localdate()
    if assignment.date < today - timedelta(days=WORKER_HOURS_LOOKBACK_DAYS):
        return _mine_row(request, assignment, _("You can only change hours from the last 7 days onward."))
    if request.POST.get("action") == "reset":
        assignment.start_time_override = None
        assignment.end_time_override = None
        assignment.times_set_by = None
        assignment.times_set_at = None
        assignment.save()
        return _mine_row(request, assignment, "")
    start_raw = request.POST.get("start_time") or ""
    end_raw = request.POST.get("end_time") or ""
    if not start_raw or not end_raw:
        return _mine_row(request, assignment, _("Enter both a start and an end time."))
    start_t = time.fromisoformat(start_raw)
    end_t = time.fromisoformat(end_raw)
    total, _after = clock_length(start_t, end_t)
    if total <= 0 or total > WORKER_HOURS_MAX_MINUTES:
        return _mine_row(request, assignment, _("This shift must be longer than 0 hours and no more than 16 hours."))
    try:
        start_dt, end_dt = interval_for(assignment.date, start_t, end_t)
    except ValueError as exc:
        return _mine_row(request, assignment, str(exc))
    other = neighbor_conflict(assignment, start_dt, end_dt, exclude_pk=assignment.pk)
    if other:
        return _mine_row(request, assignment, overlap_message(other))
    assignment.start_time_override = start_t
    assignment.end_time_override = end_t
    assignment.times_set_by = request.user
    assignment.times_set_at = timezone.now()
    assignment.save()
    return _mine_row(request, assignment, "")


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


def _mine_row(request, assignment, error):
    return render(request, "shifts/mine_row.html", {"assignment": assignment, "error": error})


def _check_in_context(assignment, now):
    if assignment is None:
        return None
    if assignment.checked_in_at:
        return {"assignment": assignment, "state": "checked", "hint": ""}
    state = check_in_state(assignment, now)
    hint = ""
    if state == "early":
        hint = _("You can check in from 30 minutes before this shift starts.")
    elif state == "closed":
        hint = _("This shift has ended.")
    return {"assignment": assignment, "state": state, "hint": hint}


def _viewer_check_in(request):
    if request.user.user_type != "support":
        return None
    today = timezone.localdate()
    assignment = (
        ShiftAssignment.objects.filter(user=request.user, date=today, shift_type__is_night=False)
        .select_related("shift_type")
        .first()
    )
    return _check_in_context(assignment, timezone.now())


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
    if assignment.shift_type.is_night:
        return _forbid()
    if assignment.date != timezone.localdate():
        return _forbid()
    now = timezone.now()
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
    assignment.save(update_fields=["checked_in_at", "updated_at"])
    return render(request, "shifts/check_in_panel.html", {"assignment": assignment, "state": "checked"})
