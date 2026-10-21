from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _


def csrf_failure(request, reason=""):
    """CSRF_FAILURE_VIEW: a stale token, usually a page left open across a sign-in.

    Signing in rotates the CSRF secret, so any form rendered before that fails.
    HTMX reloads the page (fresh token, and the login page sends a signed-in
    user on); a plain form gets a branded page with a way back.
    """
    if request.headers.get("HX-Request"):
        messages.warning(request, _(
            "Your session changed, for example after signing in on another tab. Please try again."
        ))
        response = HttpResponse(status=403)
        # htmx acts on HX-Refresh before it looks at the status.
        response["HX-Refresh"] = "true"
        return response
    back = request.headers.get("Referer") or ""
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        back = request.path
    return render(request, "csrf_failure.html", {"back_url": back}, status=403)
