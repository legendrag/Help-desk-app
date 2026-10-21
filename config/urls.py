from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.urls import include, path
from django.views.static import serve

from django.shortcuts import redirect
from django.views.generic.base import RedirectView

from accounts.template_views import set_language
from core.pwa_views import service_worker, web_manifest

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.ico', permanent=True)),
    # Same URL and name as django.conf.urls.i18n, but also saves the choice on the account.
    path("i18n/setlang/", set_language, name="set_language"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("core/", include("core.urls")),
    path("tickets/", include("tickets.urls")),
    path("notifications/", include("notifications.urls")),
    path("news/", include("news.urls")),
    path("kb/", include("kb.urls")),
    path("shifts/", include("shifts.urls")),
    path("webpush/", include("webpush.urls")),
    path("manifest.webmanifest", web_manifest, name="web_manifest"),
    path("sw.js", service_worker, name="sw.js"),
    path("", lambda r: redirect('tickets_list'), name='root'),
]

def _block_public_kb_media(request, path=""):
    """KB files are not part of the public media tree in any environment."""
    raise Http404()


@login_required
def _protected_media(request, path):
    """Serve ticket attachments to users who can view the ticket.

    Daphne serves the app directly (no reverse proxy), so this route must exist
    with DEBUG=0 too, otherwise every chat attachment 404s. KB paths stay blocked.
    """
    from tickets.access import user_can_view_ticket
    from tickets.models import Ticket

    parts = (path or "").lstrip("/").split("/")
    if len(parts) < 3 or parts[0] != "tickets" or not parts[1].isdigit():
        raise Http404()
    ticket = Ticket.objects.filter(pk=int(parts[1])).first()
    if ticket is None or not user_can_view_ticket(request.user, ticket):
        raise Http404()
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [
    path("media/kb/<path:path>", _block_public_kb_media),
    path("media/kb", _block_public_kb_media),
    path("media/<path:path>", _protected_media),
]
