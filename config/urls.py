from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path
from django.views.static import serve

from django.shortcuts import redirect
from django.views.generic.base import RedirectView

from core.pwa_views import service_worker, web_manifest

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.ico', permanent=True)),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("core/", include("core.urls")),
    path("tickets/", include("tickets.urls")),
    path("notifications/", include("notifications.urls")),
    path("news/", include("news.urls")),
    path("kb/", include("kb.urls")),
    path("webpush/", include("webpush.urls")),
    path("manifest.webmanifest", web_manifest, name="web_manifest"),
    path("sw.js", service_worker, name="sw.js"),
    path("", lambda r: redirect('tickets_list'), name='root'),
]

def _block_public_kb_media(request, path=""):
    """KB files are not part of the public media tree in any environment."""
    raise Http404()


def _protected_media(request, path):
    """Other uploads can use Django's debug media helper. KB paths stay blocked."""
    normalized = (path or "").lstrip("/")
    if normalized == "kb" or normalized.startswith("kb/"):
        raise Http404()
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [
    path("media/kb/<path:path>", _block_public_kb_media),
    path("media/kb", _block_public_kb_media),
]

if settings.DEBUG:
    urlpatterns += [
        path("media/<path:path>", _protected_media),
    ]
