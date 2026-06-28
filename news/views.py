from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import HttpResponse
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

class NewsCreateView(LoginRequiredMixin, NewsPermissionMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "news/form_partial.html"
    success_url = reverse_lazy("news_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class NewsUpdateView(LoginRequiredMixin, NewsPermissionMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "news/form_partial.html"
    success_url = reverse_lazy("news_list")

class NewsDeleteView(LoginRequiredMixin, NewsPermissionMixin, DeleteView):
    model = Announcement
    success_url = reverse_lazy("news_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get("HX-Request"):
            return HttpResponse(status=200)
        return super().delete(request, *args, **kwargs)
