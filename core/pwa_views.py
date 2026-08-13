"""Serve the web app manifest without a UTF-8 BOM.

Editors on Windows often save JSON with a BOM. Chromium then fails to parse the
manifest, so beforeinstallprompt never fires and Install never appears.
"""

from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def web_manifest(request):
    path = Path(settings.BASE_DIR) / "static" / "manifest.json"
    # utf-8-sig strips a leading BOM if present.
    text = path.read_text(encoding="utf-8-sig")
    return HttpResponse(
        text,
        content_type="application/manifest+json; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, max-age=0, must-revalidate",
        },
    )
