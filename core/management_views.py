from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render

from notifications.email_messages import (
    EVENT_META,
    chips_html_to_tokens,
    ensure_email_designer_defaults,
    get_email_brand,
    merge_fields_for_event,
    render_token_string,
    sample_context_for_event,
    tokens_to_chips_html,
)
from .models import Branch, Department, Category, Role, EmailBrand, EmailMessage, EmailSetting
from .forms import (
    BranchForm,
    DepartmentForm,
    CategoryForm,
    RoleForm,
    EmailBrandForm,
    EmailMessageForm,
    EmailSettingForm,
)

class BaseSettingsRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_access_settings)

class BranchPermissionMixin(BaseSettingsRequiredMixin):
    def test_func(self):
        if not super().test_func(): return False
        role = self.request.user.role
        if self.request.user.is_superuser: return True
        if self.request.method == 'GET': return True # List/View is allowed if you can access settings
        if 'delete' in self.request.path: return role and role.can_delete_branch
        if 'edit' in self.request.path: return role and role.can_update_branch
        if 'add' in self.request.path: return role and role.can_create_branch
        return False

class DepartmentPermissionMixin(BaseSettingsRequiredMixin):
    def test_func(self):
        if not super().test_func(): return False
        role = self.request.user.role
        if self.request.user.is_superuser: return True
        if self.request.method == 'GET': return True 
        if 'delete' in self.request.path: return role and role.can_delete_department
        if 'edit' in self.request.path: return role and role.can_update_department
        if 'add' in self.request.path: return role and role.can_create_department
        return False

class CategoryPermissionMixin(BaseSettingsRequiredMixin):
    def test_func(self):
        if not super().test_func(): return False
        role = self.request.user.role
        if self.request.user.is_superuser: return True
        if self.request.method == 'GET': return True 
        if 'delete' in self.request.path: return role and role.can_delete_category
        if 'edit' in self.request.path: return role and role.can_update_category
        if 'add' in self.request.path: return role and role.can_create_category
        return False

class RolePermissionMixin(BaseSettingsRequiredMixin):
    def test_func(self):
        if not super().test_func(): return False
        role = self.request.user.role
        if self.request.user.is_superuser: return True
        if self.request.method == 'GET': return True 
        if 'delete' in self.request.path: return role and role.can_delete_role
        if 'edit' in self.request.path: return role and role.can_update_role
        if 'add' in self.request.path: return role and role.can_create_role
        return False

class EmailPermissionMixin(BaseSettingsRequiredMixin):
    def test_func(self):
        if not super().test_func(): return False
        role = self.request.user.role
        if self.request.user.is_superuser: return True
        if self.request.method == 'GET': return True 
        return role and role.can_manage_email

class BaseManagementView:
    def form_valid(self, form):
        # We assume this is mixed into a View class
        response = super().form_valid(form)
        if hasattr(self, 'request') and self.request.headers.get('HX-Request'):
            resp = HttpResponse(status=204)
            resp['HX-Trigger'] = 'closeModal,refreshSettings'
            return resp
        return response

    def get_template_names(self):
        if hasattr(self, 'request') and self.request.headers.get('HX-Request'):
            return [self.partial_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, 'model'):
            context['model_name'] = self.model._meta.verbose_name.title()
        return context

# Branch Views
class BranchCreateView(BranchPermissionMixin, LoginRequiredMixin, BaseManagementView, CreateView):
    model = Branch
    form_class = BranchForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class BranchUpdateView(BranchPermissionMixin, LoginRequiredMixin, BaseManagementView, UpdateView):
    model = Branch
    form_class = BranchForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

# Add similar for others...
class DepartmentCreateView(DepartmentPermissionMixin, LoginRequiredMixin, BaseManagementView, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class DepartmentUpdateView(DepartmentPermissionMixin, LoginRequiredMixin, BaseManagementView, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class CategoryCreateView(CategoryPermissionMixin, LoginRequiredMixin, BaseManagementView, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class CategoryUpdateView(CategoryPermissionMixin, LoginRequiredMixin, BaseManagementView, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class RoleCreateView(RolePermissionMixin, LoginRequiredMixin, BaseManagementView, CreateView):
    model = Role
    form_class = RoleForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class RoleUpdateView(RolePermissionMixin, LoginRequiredMixin, BaseManagementView, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

    def get_queryset(self):
        return super().get_queryset().exclude(name__iexact="admin")

class EmailSettingCreateView(EmailPermissionMixin, LoginRequiredMixin, BaseManagementView, CreateView):
    model = EmailSetting
    form_class = EmailSettingForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

class EmailSettingUpdateView(EmailPermissionMixin, LoginRequiredMixin, BaseManagementView, UpdateView):
    model = EmailSetting
    form_class = EmailSettingForm
    template_name = "core/management/form.html"
    partial_template_name = "core/management/form_partial.html"
    success_url = reverse_lazy('settings')

# Delete Views (simplified)
class BaseDeleteView(LoginRequiredMixin):
    template_name = "core/management/delete_confirm.html"
    partial_template_name = "core/management/delete_confirm_partial.html"
    success_url = reverse_lazy('settings')

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if self.request.headers.get('HX-Request'):
            from django.http import HttpResponse
            resp = HttpResponse(status=204)
            resp['HX-Trigger'] = 'closeModal,refreshSettings'
            return resp
        return response

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return [self.partial_template_name]
        return [self.template_name]

class BranchDeleteView(BranchPermissionMixin, BaseDeleteView, DeleteView):
    model = Branch

class DepartmentDeleteView(DepartmentPermissionMixin, BaseDeleteView, DeleteView):
    model = Department

class CategoryDeleteView(CategoryPermissionMixin, BaseDeleteView, DeleteView):
    model = Category

class RoleDeleteView(RolePermissionMixin, BaseDeleteView, DeleteView):
    model = Role

    def get_queryset(self):
        return super().get_queryset().exclude(name__iexact="admin")

class EmailSettingDeleteView(EmailPermissionMixin, BaseDeleteView, DeleteView):
    model = EmailSetting

# List Views
class BranchListView(BranchPermissionMixin, LoginRequiredMixin, ListView):
    model = Branch
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
            'model_name': 'Branches',
            'create_url': reverse_lazy('branch_create'),
            'edit_url_prefix': '/core/branches/',
            'has_code': True,
            'can_add': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_create_branch),
            'can_edit': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_update_branch),
            'can_delete': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_delete_branch)
        })
        return context

class DepartmentListView(DepartmentPermissionMixin, LoginRequiredMixin, ListView):
    model = Department
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
            'model_name': 'Departments',
            'create_url': reverse_lazy('department_create'),
            'edit_url_prefix': '/core/departments/',
            'can_add': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_create_department),
            'can_edit': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_update_department),
            'can_delete': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_delete_department)
        })
        return context

class CategoryListView(CategoryPermissionMixin, LoginRequiredMixin, ListView):
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
            'model_name': 'Categories',
            'create_url': reverse_lazy('category_create'),
            'edit_url_prefix': '/core/categories/',
            'has_dept': True,
            'can_add': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_create_category),
            'can_edit': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_update_category),
            'can_delete': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_delete_category)
        })
        return context

class RoleListView(RolePermissionMixin, LoginRequiredMixin, ListView):
    model = Role
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
            'model_name': 'Roles',
            'create_url': reverse_lazy('role_create'),
            'edit_url_prefix': '/core/roles/',
            'can_add': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_create_role),
            'can_edit': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_update_role),
            'can_delete': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_delete_role)
        })
        return context


def _can_manage_email(user) -> bool:
    return bool(
        user.is_superuser or (user.role and user.role.can_manage_email)
    )


def _designer_canvas_context(event_type: str, can_edit: bool) -> dict:
    ensure_email_designer_defaults()
    brand = get_email_brand()
    message = get_object_or_404(EmailMessage, event_type=event_type)
    meta = next((m for m in EVENT_META if m["event_type"] == event_type), None)
    if not meta:
        raise Http404("Unknown email type")
    sample = sample_context_for_event(event_type, brand.brand_name)
    return {
        "brand": brand,
        "message": message,
        "event_meta": meta,
        "event_type": event_type,
        "merge_fields": merge_fields_for_event(event_type),
        "can_edit_email_format": can_edit,
        "region_html": {
            "subject": tokens_to_chips_html(message.subject, event_type),
            "title": tokens_to_chips_html(message.title, event_type),
            "opening": tokens_to_chips_html(message.opening, event_type),
            "message_label": tokens_to_chips_html(message.message_label, event_type),
            "button_label": tokens_to_chips_html(message.button_label, event_type),
        },
        "sample_preview": {
            "subject": render_token_string(message.subject, sample, fallback=message.subject),
            "title": render_token_string(message.title, sample, fallback=message.title),
            "opening": render_token_string(message.opening, sample, fallback=message.opening),
            "message_label": render_token_string(
                message.message_label, sample, fallback=message.message_label or "Request"
            ),
            "button_label": render_token_string(
                message.button_label, sample, fallback=message.button_label or "Open"
            ),
        },
    }


class EmailSettingListView(EmailPermissionMixin, LoginRequiredMixin, ListView):
    model = EmailSetting
    template_name = "core/management/email_settings_list.html"
    context_object_name = "object_list"

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return [self.template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_manage = _can_manage_email(self.request.user)
        ensure_email_designer_defaults()
        selected = self.request.GET.get("email_type") or "new_ticket"
        if not any(m["event_type"] == selected for m in EVENT_META):
            selected = "new_ticket"
        context.update({
            'model_name': 'Email Settings',
            'create_url': reverse_lazy('email_setting_create'),
            'edit_url_prefix': '/core/email-settings/',
            'can_add': can_manage,
            'can_edit': can_manage,
            'can_delete': can_manage,
            'can_edit_email_format': can_manage,
            'email_brand': get_email_brand(),
            'email_event_types': EVENT_META,
            'selected_email_type': selected,
            **_designer_canvas_context(selected, can_manage),
        })
        return context


class EmailDesignerCanvasView(EmailPermissionMixin, LoginRequiredMixin, View):
    def get(self, request, event_type):
        can_manage = _can_manage_email(request.user)
        context = _designer_canvas_context(event_type, can_manage)
        context["email_brand"] = context["brand"]
        return render(request, "core/management/email_designer_canvas.html", context)


class EmailBrandSaveView(EmailPermissionMixin, LoginRequiredMixin, View):
    def post(self, request):
        brand = EmailBrand.load()
        form = EmailBrandForm(request.POST, instance=brand)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        form.save()
        if request.headers.get("HX-Request"):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = "emailDesignerSaved"
            return resp
        return JsonResponse({"ok": True})


class EmailMessageSaveView(EmailPermissionMixin, LoginRequiredMixin, View):
    def post(self, request, event_type):
        message = get_object_or_404(EmailMessage, event_type=event_type)
        data = {
            "subject": chips_html_to_tokens(request.POST.get("subject_html", "")),
            "title": chips_html_to_tokens(request.POST.get("title_html", "")),
            "opening": chips_html_to_tokens(request.POST.get("opening_html", "")),
            "message_label": chips_html_to_tokens(request.POST.get("message_label_html", "")),
            "button_label": chips_html_to_tokens(request.POST.get("button_label_html", "")),
        }
        # Also accept plain token fields if posted directly.
        for key in ("subject", "title", "opening", "message_label", "button_label"):
            if request.POST.get(key) is not None and not request.POST.get(f"{key}_html"):
                data[key] = request.POST.get(key, "")
        form = EmailMessageForm(data, instance=message)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        form.save()
        if request.headers.get("HX-Request"):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = "emailDesignerSaved"
            return resp
        return JsonResponse({"ok": True})
