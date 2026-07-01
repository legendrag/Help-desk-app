from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, HttpResponse
from django.db.models import Q
from .models import Article, Category, ArticleAttachment
from .forms import ArticleForm

class KBPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.role and getattr(user.role, 'can_access_kb', False)

class ArticleListView(LoginRequiredMixin, KBPermissionMixin, ListView):
    model = Article
    template_name = "kb/list.html"
    context_object_name = "articles"

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Determine if we should show drafts
        status_filter = self.request.GET.get('status', 'published')
        can_manage = self.request.user.is_superuser or (self.request.user.role and getattr(self.request.user.role, 'can_manage_kb', False))
        
        if status_filter == 'draft' and can_manage:
            qs = qs.filter(is_published=False)
        else:
            qs = qs.filter(is_published=True)
            
        # Search
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
        
        # Category filter
        cat = self.request.GET.get('category')
        if cat and cat != 'all':
            qs = qs.filter(category_id=cat)
            
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = Category.objects.all()
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_category'] = self.request.GET.get('category', '')
        ctx['current_status'] = self.request.GET.get('status', 'published')
        ctx['can_manage_kb'] = self.request.user.is_superuser or (self.request.user.role and getattr(self.request.user.role, 'can_manage_kb', False))
        
        if ctx['can_manage_kb']:
            ctx['draft_count'] = Article.objects.filter(is_published=False).count()
            
        return ctx

class ArticleDetailView(LoginRequiredMixin, KBPermissionMixin, DetailView):
    model = Article
    template_name = "kb/detail.html"
    context_object_name = "article"

class ArticleCreateView(LoginRequiredMixin, KBPermissionMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = "kb/form.html"

    def form_valid(self, form):
        action = self.request.POST.get('action')
        form.instance.is_published = (action != 'draft')
        form.instance.created_by = self.request.user
        self.object = form.save()
        attachments = self.request.FILES.getlist('attachments')
        for f in attachments:
            ArticleAttachment.objects.create(article=self.object, file=f)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("kb_detail", kwargs={"pk": self.object.pk})

class ArticleUpdateView(LoginRequiredMixin, KBPermissionMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = "kb/form.html"

    def form_valid(self, form):
        action = self.request.POST.get('action')
        form.instance.is_published = (action != 'draft')
        self.object = form.save()
        attachments = self.request.FILES.getlist('attachments')
        for f in attachments:
            ArticleAttachment.objects.create(article=self.object, file=f)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("kb_detail", kwargs={"pk": self.object.pk})

class ArticleDeleteView(LoginRequiredMixin, KBPermissionMixin, DeleteView):
    model = Article
    success_url = reverse_lazy("kb_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get("HX-Request"):
            return HttpResponse(status=200)
        return super().delete(request, *args, **kwargs)
