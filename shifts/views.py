from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import get_language, gettext as _
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.http_cache import apply_read_etag, etag_digest, htmx_not_modified, htmx_revalidation_match
from core.models import Department
from shifts.access import display_name, home_target, is_shift_manager
from shifts.forms import ShiftTypeForm
from shifts.models import ShiftAssignment, ShiftType
from shifts.services import (
    effective_times,
    interval_for,
    month_dates,
    neighbor_conflict,
    normalize_start,
    overlap_message,
    overrides_set_by_worker,
    week_dates,
)

User = get_user_model()


def _forbid():
    return HttpResponseForbidden(_("You cannot open this page."))


def _shell(request, template, context):
    context["is_manager"] = is_shift_manager(request.user)
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
    for row in visible:
        row.set_by_worker = overrides_set_by_worker(row)
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
    return _shell(request, "shifts/mine.html", {})


@login_required
@require_GET
def shifts_available(request):
    return _shell(request, "shifts/available.html", {})


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
