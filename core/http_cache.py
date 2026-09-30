"""Conditional reads for shell panes.

Ticket-list polls already return 304 when the client repeats If-None-Match.
Other read-only panes can do the same, but only for an HTMX revalidation.
History restore and load-more still need a body. Authenticated 200s stay on
the no-store family via NoCacheAfterLogoutMiddleware; the private, no-cache
marker here matches the ticket-list response before that middleware runs.
"""

import hashlib

from django.http import HttpResponseNotModified
from django.utils.cache import patch_vary_headers


def etag_digest(parts):
    raw = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f'"{digest}"'


def htmx_revalidation_match(request, etag):
    """True when this HTMX GET may keep the pane already on screen."""
    if not etag or not request.headers.get("HX-Request"):
        return False
    if request.headers.get("HX-History-Restore-Request"):
        return False
    if request.GET.get("append") == "true":
        return False
    return request.headers.get("If-None-Match") == etag


def htmx_not_modified(etag):
    response = HttpResponseNotModified()
    response["ETag"] = etag
    response["Cache-Control"] = "private, no-cache"
    patch_vary_headers(response, ["HX-Request"])
    return response


def apply_read_etag(response, etag, request):
    if etag:
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-cache"
    if request.headers.get("HX-Request"):
        patch_vary_headers(response, ["HX-Request"])
    return response
