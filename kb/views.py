import mimetypes
from pathlib import Path

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Count, Case, When, Value, IntegerField, Max
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.cache import patch_vary_headers
from django.utils.html import format_html
from django.utils.translation import get_language, gettext as _
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from core.http_cache import apply_read_etag, etag_digest, htmx_not_modified, htmx_revalidation_match
from core.pagination import KnownCountPaginator
from core.management_views import BaseManagementView, BaseDeleteView
from tickets.access import user_can_view_ticket
from tickets.models import Ticket
from tickets.search import apply_ticket_search

from .access import articles_for_user, published_visibility_q, user_can_manage_kb, user_can_read_kb
from .forms import ArticleForm, KBCategoryForm
from .models import Article, ArticleAttachment, Category


def _user_can_manage_kb(user):
    return user_can_manage_kb(user)


def _base_articles_qs(user, status_filter="published"):
    if status_filter == "draft" and _user_can_manage_kb(user):
        qs = Article.objects.filter(is_published=False)
    else:
        qs = articles_for_user(user, include_drafts=False)
    return qs.select_related("category", "created_by")


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


class KBPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return user_can_read_kb(self.request.user)


class KBManageMixin(UserPassesTestMixin):
    """Create, edit, delete, and drafts require can_manage_kb, not only read access."""

    def test_func(self):
        return user_can_manage_kb(self.request.user)

class ArticleListView(LoginRequiredMixin, KBPermissionMixin, ListView):
    model = Article
    template_name = "kb/list.html"
    context_object_name = "articles"
    paginate_by = 8

    def _filter_state(self):
        request = self.request
        search_query = (request.GET.get("q") or "").strip()
        category_ids = [
            c for c in request.GET.getlist("category") if str(c).isdigit()
        ]
        status_filter = request.GET.get("status", "published")
        sort = request.GET.get("sort", "relevance" if search_query else "newest")
        return search_query, category_ids, status_filter, sort

    def _is_browse_home(self):
        search_query, category_ids, status_filter, _sort = self._filter_state()
        return not search_query and not category_ids and status_filter != "draft"

    def _skip_page_rows(self):
        # Browse home paints category tiles and six recent titles. The page
        # of article bodies is not in that template.
        if self.request.GET.get("append") == "true":
            return False
        return self._is_browse_home()

    def _perm_signature(self, user):
        if user.is_superuser:
            return "su"
        role = getattr(user, "role", None)
        if not role:
            return "none"
        flags = (
            "can_manage_kb",
            "can_access_settings",
            "can_create_ticket",
            "can_access_kb",
        )
        return "".join("1" if getattr(role, flag, False) else "0" for flag in flags)

    def _article_stats(self):
        if hasattr(self, "_article_count"):
            return self._article_count, self._article_max
        user = self.request.user
        search_query, category_ids, status_filter, _sort = self._filter_state()
        # No select_related: COUNT/MAX does not need category or author joins.
        stats_qs = _base_articles_qs(user, status_filter).select_related(None)
        if search_query:
            stats_qs = stats_qs.filter(
                Q(title__icontains=search_query) | Q(content__icontains=search_query)
            )
        if category_ids:
            stats_qs = stats_qs.filter(category_id__in=category_ids)
        stats = stats_qs.aggregate(count=Count("id"), max_updated=Max("updated_at"))
        self._article_count = stats["count"] or 0
        self._article_max = stats["max_updated"]
        return self._article_count, self._article_max

    def _category_signature(self, categories=None):
        if categories is None:
            rows = list(
                Category.objects.order_by("id").values_list(
                    "id", "name", "description", "icon"
                )
            )
        else:
            rows = sorted(
                (
                    (category.id, category.name, category.description, category.icon)
                    for category in categories
                ),
                key=lambda row: row[0],
            )
        return etag_digest([repr(rows)])

    def _list_etag(self, categories=None):
        request = self.request
        user = request.user
        search_query, _category_ids, status_filter, sort = self._filter_state()
        count, max_updated = self._article_stats()
        can_manage = _user_can_manage_kb(user)
        draft_count = 0
        if can_manage:
            draft_count = getattr(self, "_draft_count", None)
            if draft_count is None:
                draft_count = Article.objects.filter(is_published=False).count()
                self._draft_count = draft_count
        return etag_digest(
            [
                get_language(),
                self._perm_signature(user),
                search_query,
                status_filter,
                sort,
                ",".join(_category_ids),
                request.GET.get("page", ""),
                count,
                max_updated.isoformat() if max_updated else "",
                draft_count,
                self._category_signature(categories),
            ]
        )

    def get(self, request, *args, **kwargs):
        etag = None
        is_append = request.GET.get("append") == "true"
        if not is_append:
            # Repeat views can 304 off the aggregate. First paint skips the
            # category-signature query and hashes the categories it already loads.
            if request.headers.get("If-None-Match"):
                etag = self._list_etag()
                self._shell_etag_value = etag
                if htmx_revalidation_match(request, etag):
                    return htmx_not_modified(etag)
            else:
                self._article_stats()
        response = super().get(request, *args, **kwargs)
        if etag is None and not is_append:
            etag = getattr(self, "_shell_etag_value", None)
        return apply_read_etag(response, etag, request)

    def get_paginator(self, queryset, per_page, orphans=0, allow_empty_first_page=True, **kwargs):
        known = None
        if not self._skip_page_rows():
            known = getattr(self, "_article_count", None)
        return KnownCountPaginator(
            queryset,
            per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
            known_count=known,
        )

    def get_template_names(self):
        # Load-more appends rows. Shell navigation and back/forward need the
        # whole knowledge-base pane, not that fragment.
        if (
            self.request.headers.get("HX-Request")
            and self.request.GET.get("append") == "true"
            and not self.request.headers.get("HX-History-Restore-Request")
        ):
            return ["kb/partials/results_append.html"]
        if self.request.headers.get("HX-Request"):
            return ["kb/list_shell_partial.html"]
        return [self.template_name]

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        if self.request.headers.get("HX-Request"):
            patch_vary_headers(response, ["HX-Request"])
        return response

    def paginate_queryset(self, queryset, page_size):
        # An empty stand-in queryset has no page 2. Browse home ignores the
        # page list, so a ?page= request must stay a 200 of that home.
        if self._skip_page_rows():
            paginator = self.get_paginator(
                queryset,
                page_size,
                orphans=self.get_paginate_orphans(),
                allow_empty_first_page=self.get_allow_empty(),
            )
            return (paginator, None, queryset, False)
        return super().paginate_queryset(queryset, page_size)

    def get_queryset(self):
        if self._skip_page_rows():
            return Article.objects.none().only("id")
        status_filter = self.request.GET.get("status", "published")
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

        sort = self.request.GET.get("sort", "")
        return _apply_sort(qs, sort, search_query)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        search_query, category_ids, status_filter, sort = self._filter_state()
        is_append = (
            request.headers.get("HX-Request")
            and request.GET.get("append") == "true"
            and not request.headers.get("HX-History-Restore-Request")
        )

        ctx["search_query"] = search_query
        ctx["shell_etag"] = getattr(self, "_shell_etag_value", "")
        params = request.GET.copy()
        params.pop("page", None)
        params.pop("append", None)
        ctx["filter_query"] = params.urlencode()
        # Load-more only appends result rows and the next button.
        if is_append:
            return ctx

        can_manage = _user_can_manage_kb(request.user)
        ctx["categories"] = Category.objects.annotate(
            article_count=Count(
                "articles",
                filter=published_visibility_q(request.user, prefix="articles__"),
            )
        )
        ctx["current_categories"] = category_ids
        ctx["current_status"] = status_filter
        ctx["current_sort"] = sort
        ctx["can_manage_kb"] = can_manage
        ctx["can_access_settings"] = request.user.is_superuser or (
            request.user.role and getattr(request.user.role, "can_access_settings", False)
        )
        ctx["can_create_ticket"] = request.user.is_superuser or (
            request.user.role and getattr(request.user.role, "can_create_ticket", False)
        )

        paginator = ctx.get("paginator")
        ctx["article_count"] = paginator.count if paginator else len(ctx["articles"])

        is_browse_home = self._is_browse_home()
        ctx["is_browse_home"] = is_browse_home

        if can_manage:
            draft_count = getattr(self, "_draft_count", None)
            if draft_count is None:
                draft_count = Article.objects.filter(is_published=False).count()
                self._draft_count = draft_count
            ctx["draft_count"] = draft_count

        if not getattr(self, "_shell_etag_value", None):
            self._shell_etag_value = self._list_etag(ctx["categories"])
        ctx["shell_etag"] = self._shell_etag_value

        if is_browse_home:
            ctx["recent_articles"] = list(
                articles_for_user(request.user, include_drafts=False)
                .select_related("category")
                .only(
                    "title",
                    "updated_at",
                    "category",
                    "category__name",
                    "category__icon",
                )
                .order_by("-updated_at")[:6]
            )

        params_no_q = request.GET.copy()
        params_no_q.pop("page", None)
        params_no_q.pop("append", None)
        params_no_q.pop("q", None)
        ctx["filter_query_no_q"] = params_no_q.urlencode()

        return ctx

class ArticleDetailView(LoginRequiredMixin, KBPermissionMixin, DetailView):
    model = Article
    template_name = "kb/detail.html"
    context_object_name = "article"

    def get_queryset(self):
        # Drafts and out-of-audience rows are excluded. Managers may open drafts.
        user = self.request.user
        return (
            articles_for_user(user, include_drafts=_user_can_manage_kb(user))
            .select_related("category", "created_by", "related_ticket")
            .prefetch_related("attachments")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        article = self.object
        user = self.request.user
        related = []
        if article.category_id:
            related = list(
                articles_for_user(user, include_drafts=False)
                .filter(category_id=article.category_id)
                .exclude(pk=article.pk)
                .select_related("category")
                .order_by("-updated_at")[:5]
            )
        ctx["related_articles"] = related
        ctx["can_manage_kb"] = _user_can_manage_kb(user)
        ticket = article.related_ticket
        ctx["can_view_related_ticket"] = bool(ticket and user_can_view_ticket(user, ticket))
        return ctx


class ArticleWriteMixin:
    """Publish actions set visibility. Save draft and autosave do not publish."""

    publish_actions = {
        Article.Visibility.ONLY_ME,
        Article.Visibility.DEPARTMENT,
        Article.Visibility.ALL_SUPPORT,
    }

    def _visibility_author(self):
        obj = getattr(self, "object", None)
        if obj is not None and getattr(obj, "created_by_id", None):
            return obj.created_by
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self._visibility_author()
        kwargs["editor"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        author = self._visibility_author()
        ctx["offer_department_visibility"] = bool(getattr(author, "department_id", None))
        return ctx

    def _is_autosave(self):
        return self.request.headers.get("X-KB-Autosave") == "1"

    def _apply_action(self, form):
        action = (self.request.POST.get("action") or "").strip()
        author = self._visibility_author()
        if action == Article.Visibility.DEPARTMENT and not getattr(author, "department_id", None):
            form.add_error("visibility", _("My department is unavailable without a department."))
            return None
        if self._is_autosave():
            already_published = bool(
                self.object and getattr(self.object, "pk", None) and self.object.is_published
            )
            form.instance.is_published = already_published
            return "autosave"
        if action == "draft":
            form.instance.is_published = False
            return "draft"
        if action in self.publish_actions:
            form.instance.is_published = True
            form.instance.visibility = action
            if action == Article.Visibility.DEPARTMENT:
                form.instance.visibility_department_id = getattr(author, "department_id", None)
            else:
                form.instance.visibility_department = None
            return "publish"
        form.instance.is_published = True
        return "publish"

    def _sync_attachments(self, form):
        remove_ids = [pk for pk in self.request.POST.getlist("remove_attachments") if str(pk).isdigit()]
        if remove_ids:
            doomed = ArticleAttachment.objects.filter(article=self.object, pk__in=remove_ids)
            for attachment in doomed:
                if attachment.file:
                    attachment.file.delete(save=False)
                attachment.delete()
        for uploaded in form.cleaned_data.get("attachments") or []:
            if uploaded:
                ArticleAttachment.objects.create(article=self.object, file=uploaded)

    def form_valid(self, form):
        if not form.instance.created_by_id:
            form.instance.created_by = self.request.user
        outcome = self._apply_action(form)
        if outcome is None:
            return self.form_invalid(form)
        self.object = form.save()
        if outcome != "autosave":
            self._sync_attachments(form)
        if outcome == "autosave":
            return JsonResponse(
                {
                    "id": self.object.pk,
                    "edit_url": reverse("kb_update", kwargs={"pk": self.object.pk}),
                    "is_published": self.object.is_published,
                }
            )
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        if self._is_autosave():
            return JsonResponse({"ok": False}, status=400)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy("kb_detail", kwargs={"pk": self.object.pk})


class ArticleCreateView(ArticleWriteMixin, LoginRequiredMixin, KBManageMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = "kb/form.html"


class ArticleUpdateView(ArticleWriteMixin, LoginRequiredMixin, KBManageMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = "kb/form.html"

    def get_queryset(self):
        user = self.request.user
        return (
            articles_for_user(user, include_drafts=True)
            .select_related(
                "category",
                "created_by",
                "related_ticket",
                "related_ticket__department",
                "related_ticket__created_by",
            )
            .prefetch_related("attachments")
        )


class ArticleDeleteView(LoginRequiredMixin, KBManageMixin, DeleteView):
    model = Article
    success_url = reverse_lazy("kb_list")

    def get_queryset(self):
        return articles_for_user(self.request.user, include_drafts=True)

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
        return user_can_manage_kb(self.request.user)

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
    if not user_can_read_kb(request.user):
        return HttpResponse(status=403)

    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return HttpResponse("")

    suggestions = (
        articles_for_user(request.user, include_drafts=False)
        .filter(title__icontains=query)
        .select_related("category")
        .order_by("-updated_at")[:5]
    )
    return render(
        request,
        "kb/partials/search_suggestions.html",
        {"suggestions": suggestions},
    )


def kb_ticket_search(request):
    if not user_can_manage_kb(request.user):
        return HttpResponse(status=403)

    user = request.user
    query = (request.GET.get("q") or "").strip()
    if len(query) < 1:
        return HttpResponse('<div id="kb-ticket-results"></div>')

    tickets = Ticket.objects.all()
    if not user.is_superuser:
        if user.user_type == "branch" and user.branch_id:
            tickets = tickets.filter(branch_id=user.branch_id)
        elif user.user_type == "support" and user.department_id:
            tickets = tickets.filter(department_id=user.department_id)
        else:
            tickets = tickets.none()

    tickets = list(
        apply_ticket_search(
            tickets.select_related("department", "branch", "created_by"),
            query,
        )[:10]
    )
    parts = ['<div id="kb-ticket-results" class="kb-ticket-results" role="listbox">']
    if not tickets:
        parts.append('<p class="kb-ticket-empty">No matching tickets found</p>')
    for ticket in tickets:
        label = f"#{ticket.ticket_number} {ticket.title}"
        parts.append(
            str(
                format_html(
                    '<button type="button" class="kb-ticket-result" role="option" data-ticket-id="{}" data-ticket-label="{}">{}</button>',
                    ticket.pk,
                    label,
                    label,
                )
            )
        )
    parts.append("</div>")
    return HttpResponse("\n".join(parts))


def kb_attachment(request, pk):
    """Download or preview an attachment after the same read check as the article."""
    if not user_can_read_kb(request.user):
        return HttpResponse(status=403)
    attachment = get_object_or_404(
        ArticleAttachment.objects.select_related("article"),
        pk=pk,
    )
    visible = articles_for_user(
        request.user,
        include_drafts=_user_can_manage_kb(request.user),
    )
    if not visible.filter(pk=attachment.article_id).exists():
        raise Http404()
    if not attachment.file or not attachment.file.name:
        raise Http404()
    try:
        handle = attachment.file.open("rb")
    except FileNotFoundError:
        raise Http404()
    content_type = mimetypes.guess_type(attachment.file.name)[0] or "application/octet-stream"
    response = FileResponse(
        handle,
        content_type=content_type,
        as_attachment=False,
        filename=Path(attachment.file.name).name,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
