from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django.shortcuts import redirect
from django.views.generic.base import RedirectView, TemplateView

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.ico', permanent=True)),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("core/", include("core.urls")),
    path("tickets/", include("tickets.urls")),
    path("notifications/", include("notifications.urls")),
    path("news/", include("news.urls")),
    path("kb/", include("kb.urls")),
    path("webpush/", include("webpush.urls")),
    path("sw.js", TemplateView.as_view(template_name="sw.js", content_type="application/javascript"), name="sw.js"),
    path("", lambda r: redirect('tickets_list'), name='root'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

