from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.models import Department
from shifts.access import home_target, is_shift_manager
from shifts.forms import ShiftTypeForm
from shifts.models import ShiftType


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


@login_required
@require_GET
def shifts_rota(request):
    if not is_shift_manager(request.user):
        return _forbid()
    return _shell(request, "shifts/rota.html", {"shell_etag": ""})


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
