from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Max, Q
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.translation import get_language

from core.http_cache import apply_read_etag, etag_digest, htmx_not_modified, htmx_revalidation_match
from notifications.services import notify_announcement_created
from .models import Announcement
from .forms import AnnouncementForm

class NewsPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return user.role and getattr(user.role, 'can_manage_news', False)

class NewsListView(LoginRequiredMixin, NewsPermissionMixin, ListView):
    model = Announcement
    template_name = "news/list.html"
    context_object_name = "announcements"

    def get_queryset(self):
        # The list paints title, status, target, author, and dates. Body HTML
        # is only used on the edit form.
        return (
            super()
            .get_queryset()
            .select_related("created_by", "target_branch")
            .only(
                "title",
                "is_active",
                "expires_at",
                "created_at",
                "target_branch",
                "target_branch__name",
                "created_by",
                "created_by__username",
            )
        )

    def _list_etag(self):
        now = timezone.now()
        stats = Announcement.objects.aggregate(
            count=Count("id"),
            max_updated=Max("updated_at"),
            expired=Count(
                "id",
                filter=Q(expires_at__isnull=False, expires_at__lte=now),
            ),
        )
        max_updated = stats["max_updated"]
        return etag_digest(
            [
                get_language(),
                stats["count"] or 0,
                stats["expired"] or 0,
                max_updated.isoformat() if max_updated else "",
            ]
        )

    def get(self, request, *args, **kwargs):
        etag = self._list_etag()
        self._shell_etag_value = etag
        if htmx_revalidation_match(request, etag):
            return htmx_not_modified(etag)
        response = super().get(request, *args, **kwargs)
        return apply_read_etag(response, etag, request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["shell_etag"] = getattr(self, "_shell_etag_value", "")
        return context

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["news/list_shell_partial.html"]
        return [self.template_name]

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        if self.request.headers.get("HX-Request"):
            patch_vary_headers(response, ["HX-Request"])
        return response


class NewsCreateView(LoginRequiredMixin, NewsPermissionMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "news/form_partial.html"
    success_url = reverse_lazy("news_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        self.object = form.save()
        notify_announcement_created(self.object, actor=self.request.user)
        if self.request.headers.get("HX-Request"):
            from django.http import HttpResponse
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = "closeModal,reloadPage"
            return resp
        return super().form_valid(form)

class NewsUpdateView(LoginRequiredMixin, NewsPermissionMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "news/form_partial.html"
    success_url = reverse_lazy("news_list")

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("HX-Request"):
            from django.http import HttpResponse
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = "closeModal,reloadPage"
            return resp
        return super().form_valid(form)

class NewsDeleteView(LoginRequiredMixin, NewsPermissionMixin, DeleteView):
    model = Announcement
    success_url = reverse_lazy("news_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get("HX-Request"):
            from django.http import HttpResponse
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = "closeModal,reloadPage"
            return resp
        return super().delete(request, *args, **kwargs)
