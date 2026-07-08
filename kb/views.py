from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, HttpResponse
from django.db.models import Q
from .models import Article, Category, ArticleAttachment
from .forms import ArticleForm, KBCategoryForm
from tickets.models import Ticket
from core.management_views import BaseManagementView, BaseDeleteView

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

# ==========================================
# KB Category Management Views
# ==========================================

class KBCategoryPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.role and getattr(user.role, 'can_manage_kb', False)

class KBCategoryListView(KBCategoryPermissionMixin, ListView):
    model = Category
    template_name = "core/management/list_partial_v2.html"
    partial_template_name = "core/management/list_partial_v2.html"
    context_object_name = "object_list"

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return [self.partial_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'model_name': 'KB Categories',
            'create_url': reverse_lazy('kb_category_create'),
            'edit_url_prefix': '/kb/categories/',
            'can_add': True,
            'can_edit': True,
            'can_delete': True
        })
        return context

class KBCategoryCreateView(KBCategoryPermissionMixin, BaseManagementView, CreateView):
    model = Category
    form_class = KBCategoryForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class KBCategoryUpdateView(KBCategoryPermissionMixin, BaseManagementView, UpdateView):
    model = Category
    form_class = KBCategoryForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class KBCategoryDeleteView(KBCategoryPermissionMixin, BaseDeleteView, DeleteView):
    model = Category
    success_url = reverse_lazy('settings')

def kb_ticket_search(request):
    user = request.user
    query = request.GET.get("q", "").strip()
    
    if len(query) < 1:
        return HttpResponse('<div id="kb-search-results-container"></div>')
        
    tickets = Ticket.objects.filter(
        Q(ticket_number__icontains=query) | Q(title__icontains=query)
    )
    
    if not user.is_superuser:
        if user.user_type == "branch" and user.branch_id:
            tickets = tickets.filter(branch_id=user.branch_id)
        elif user.user_type == "support" and user.department_id:
            tickets = tickets.filter(department_id=user.department_id)
        else:
            tickets = tickets.none()
            
    tickets = tickets.select_related("department", "branch", "created_by")[:10]
    
    if not tickets.exists():
        return HttpResponse('<div id="kb-search-results-container" class="merge-search-results"><div class="merge-search-empty">No matching tickets found</div></div>')

    options = ['<div id="kb-search-results-container" class="merge-search-results">']
    for t in tickets:
        status_label = t.get_status_display()
        priority_label = t.get_priority_display().upper()
        # Instead of going to merge-preview, we just render the ticket preview directly and set the hidden input.
        # We can use JS to set the hidden input and update a preview div.
        preview_html = (
            f'<div class="merge-preview-card margin-bottom-small">'
            f'  <div class="merge-preview-header">'
            f'    <span class="merge-preview-num">#{t.ticket_number}</span>'
            f'    <div class="merge-preview-badges">'
            f'      <span class="badge badge-{t.status}">{status_label}</span>'
            f'      <span class="priority-badge priority-{t.priority}">{priority_label}</span>'
            f'      <button type="button" class="modal-close modal-close--sm" onclick="clearKbTicket()" title="Remove Related Ticket">'
            f'        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>'
            f'      </button>'
            f'    </div>'
            f'  </div>'
            f'  <h4 class="merge-preview-title merge-preview-title--lg">{t.title}</h4>'
            f'  <div class="merge-preview-meta-grid">'
            f'    <div class="merge-meta-item"><span class="label">Dept</span><span class="val">{t.department.name}</span></div>'
            f'    <div class="merge-meta-item"><span class="label">By</span><span class="val">{t.created_by.username}</span></div>'
            f'  </div>'
            f'</div>'
        )
        
        # Base64 encode the html for the onclick handler to avoid all quote escaping issues
        import base64
        encoded_preview = base64.b64encode(preview_html.encode('utf-8')).decode('utf-8')
        
        options.append(
            f'<div class="merge-search-item" '
            f'onclick="selectKbTicket(\'{t.id}\', \'{encoded_preview}\')">'
            f'  <div class="merge-item-header">'
            f'    <span class="merge-item-number">{t.ticket_number}</span>'
            f'    <div class="merge-item-badges">'
            f'      <span class="badge badge-{t.status}">{status_label}</span>'
            f'    </div>'
            f'  </div>'
            f'  <div class="merge-item-title">{t.title}</div>'
            f'</div>'
        )
    options.append('</div>')
    
    return HttpResponse("\n".join(options))
