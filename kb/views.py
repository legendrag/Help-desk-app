from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from core.management_views import BaseManagementView, BaseDeleteView
from tickets.models import Ticket

from .forms import ArticleForm, KBCategoryForm
from .models import Article, ArticleAttachment, Category


def _user_can_manage_kb(user):
    return user.is_superuser or (
        user.role and getattr(user.role, "can_manage_kb", False)
    )


def _published_filter_for_status(status_filter, can_manage):
    if status_filter == "draft" and can_manage:
        return Q(articles__is_published=False)
    return Q(articles__is_published=True)


def _base_articles_qs(user, status_filter="published"):
    can_manage = _user_can_manage_kb(user)
    qs = Article.objects.select_related("category", "created_by")
    if status_filter == "draft" and can_manage:
        return qs.filter(is_published=False)
    return qs.filter(is_published=True)


def _apply_updated_filter(qs, updated):
    if updated in ("7", "30", "90"):
        since = timezone.now() - timedelta(days=int(updated))
        return qs.filter(updated_at__gte=since)
    return qs


def _apply_sort(qs, sort, search_query):
    q = (search_query or "").strip()
    if sort == "oldest":
        return qs.order_by("updated_at")
    if sort == "newest":
        return qs.order_by("-updated_at")
    if q and (sort == "relevance" or not sort):
        return qs.annotate(
            relevance=Case(
                When(title__icontains=q, then=Value(3)),
                When(content__icontains=q, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by("-relevance", "-updated_at")
    return qs.order_by("-updated_at")


def _get_suggested_articles(user, status_filter, search_query, category_ids, exclude_ids):
    qs = _base_articles_qs(user, status_filter)
    if search_query:
        match = qs.filter(
            Q(title__icontains=search_query) | Q(content__icontains=search_query)
        ).first()
        if match and match.category_id:
            qs = qs.filter(category_id=match.category_id)
        elif category_ids:
            qs = qs.filter(category_id__in=category_ids)
    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)
    suggested = list(qs.order_by("-updated_at")[:5])
    if len(suggested) < 3:
        fallback = _base_articles_qs(user, status_filter).order_by("-updated_at")[:5]
        seen = {a.pk for a in suggested}
        for article in fallback:
            if article.pk not in seen:
                suggested.append(article)
                seen.add(article.pk)
            if len(suggested) >= 5:
                break
    return suggested[:5]

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
    paginate_by = 8

    def get_queryset(self):
        status_filter = self.request.GET.get("status", "published")
        can_manage = _user_can_manage_kb(self.request.user)
        qs = _base_articles_qs(self.request.user, status_filter)

        search_query = (self.request.GET.get("q") or "").strip()
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) | Q(content__icontains=search_query)
            )

        category_ids = [
            c for c in self.request.GET.getlist("category") if str(c).isdigit()
        ]
        if category_ids:
            qs = qs.filter(category_id__in=category_ids)

        updated = self.request.GET.get("updated", "any")
        qs = _apply_updated_filter(qs, updated)

        sort = self.request.GET.get("sort", "")
        return _apply_sort(qs, sort, search_query)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        can_manage = _user_can_manage_kb(request.user)
        status_filter = request.GET.get("status", "published")
        search_query = (request.GET.get("q") or "").strip()
        category_ids = [
            c for c in request.GET.getlist("category") if str(c).isdigit()
        ]
        updated_filter = request.GET.get("updated", "any")
        sort = request.GET.get("sort", "relevance" if search_query else "newest")

        published_filter = _published_filter_for_status(status_filter, can_manage)
        ctx["categories"] = Category.objects.annotate(
            article_count=Count("articles", filter=published_filter)
        )
        ctx["search_query"] = search_query
        ctx["current_categories"] = category_ids
        ctx["current_status"] = status_filter
        ctx["current_updated"] = updated_filter
        ctx["current_sort"] = sort
        ctx["can_manage_kb"] = can_manage
        ctx["can_create_ticket"] = request.user.is_superuser or (
            request.user.role and getattr(request.user.role, "can_create_ticket", False)
        )
        ctx["all_articles_count"] = _base_articles_qs(
            request.user, status_filter
        ).count()

        paginator = ctx.get("paginator")
        ctx["article_count"] = paginator.count if paginator else len(ctx["articles"])

        ctx["has_active_filters"] = bool(
            search_query
            or category_ids
            or updated_filter not in ("", "any")
            or (can_manage and status_filter == "draft")
        )

        if can_manage:
            ctx["draft_count"] = Article.objects.filter(is_published=False).count()

        article_ids = [a.pk for a in ctx["articles"]]
        ctx["suggested_articles"] = _get_suggested_articles(
            request.user,
            status_filter,
            search_query,
            category_ids,
            article_ids,
        )

        params = request.GET.copy()
        params.pop("page", None)
        ctx["filter_query"] = params.urlencode()
        params_no_q = request.GET.copy()
        params_no_q.pop("page", None)
        params_no_q.pop("q", None)
        ctx["filter_query_no_q"] = params_no_q.urlencode()

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

def kb_search_suggest(request):
    if not request.user.is_authenticated:
        return HttpResponse(status=403)

    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return HttpResponse("")

    suggestions = (
        Article.objects.filter(is_published=True, title__icontains=query)
        .select_related("category")
        .order_by("-updated_at")[:5]
    )
    return render(
        request,
        "kb/partials/search_suggestions.html",
        {"suggestions": suggestions},
    )


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
