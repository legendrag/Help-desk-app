from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from shifts.access import home_target, is_shift_manager


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
