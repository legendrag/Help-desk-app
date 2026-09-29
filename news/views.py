from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers
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
        return super().get_queryset().select_related("created_by")

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
