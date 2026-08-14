"""Serve the PWA manifest and service worker with Chrome-installable headers."""

from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_GET


def _pwa_response(body: str, content_type: str) -> HttpResponse:
    response = HttpResponse(body, content_type=content_type)
    # no-store prevents Chrome from persisting the service worker, so the
    # origin never qualifies as an installable app.
    response["Cache-Control"] = "max-age=0, must-revalidate"
    return response


@require_GET
def web_manifest(request):
    path = Path(settings.BASE_DIR) / "static" / "manifest.json"
    text = path.read_text(encoding="utf-8-sig")
    return _pwa_response(text, "application/manifest+json; charset=utf-8")


@require_GET
def service_worker(request):
    path = Path(settings.BASE_DIR) / "templates" / "sw.js"
    body = path.read_text(encoding="utf-8")
    response = _pwa_response(body, "application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    return response
