import json

from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render

from notifications.email_content import render_notification_email
from notifications.email_service import send_with_retries
from notifications.email_templates import (
    EVENT_META,
    cta_url_for_event,
    ensure_email_templates,
    get_template_defaults,
    merge_fields_for_event,
    render_subject_body,
    sample_context_for_event,
)
from .models import Branch, Department, Category, Role, EmailSetting, EmailTemplate
from .forms import (
    BranchForm,
    DepartmentForm,
    CategoryForm,
    RoleForm,
    EmailSettingForm,
    EmailTemplateForm,
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


def _email_template_form_context(event_type: str, can_edit: bool, form=None) -> dict:
    if not any(m["event_type"] == event_type for m in EVENT_META):
        raise Http404("Unknown email type")
    ensure_email_templates()
    template = get_object_or_404(EmailTemplate, event_type=event_type)
    if form is None:
        form = EmailTemplateForm(instance=template)
    defaults = get_template_defaults(event_type)
    return {
        "email_template": template,
        "email_template_form": form,
        "selected_email_type": event_type,
        "email_event_types": EVENT_META,
        "merge_fields": merge_fields_for_event(event_type),
        "can_edit_email_templates": can_edit,
        "sample_context": sample_context_for_event(event_type),
        "default_subject": defaults["subject"],
        "default_body": defaults["body"],
        "email_template_meta": {
            "event_type": event_type,
            "sample": sample_context_for_event(event_type),
            "defaults": {
                "subject": defaults["subject"],
                "body": defaults["body"],
            },
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
            **_email_template_form_context(selected, can_manage),
        })
        return context


class EmailTemplateFormPartialView(EmailPermissionMixin, LoginRequiredMixin, View):
    def get(self, request):
        event_type = request.GET.get("email_type") or "new_ticket"
        can_manage = _can_manage_email(request.user)
        context = _email_template_form_context(event_type, can_manage)
        return render(request, "core/management/email_template_form.html", context)


class EmailTemplateSaveView(EmailPermissionMixin, LoginRequiredMixin, View):
    def post(self, request, event_type):
        if not _can_manage_email(request.user):
            return JsonResponse({"ok": False, "error": "Permission denied."}, status=403)
        if not any(m["event_type"] == event_type for m in EVENT_META):
            raise Http404("Unknown email type")
        ensure_email_templates()
        template = get_object_or_404(EmailTemplate, event_type=event_type)
        form = EmailTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            context = _email_template_form_context(event_type, True)
            response = render(request, "core/management/email_template_form.html", context)
            response["HX-Trigger"] = "emailTemplateSaved"
            return response
        context = _email_template_form_context(event_type, True, form=form)
        return render(request, "core/management/email_template_form.html", context)


class EmailTemplateTestSendView(EmailPermissionMixin, LoginRequiredMixin, View):
    """Send the current form subject/body as a sample email to the signed-in user."""

    def post(self, request, event_type):
        if not _can_manage_email(request.user):
            return self._trigger_response(False, "Permission denied.")
        if not any(m["event_type"] == event_type for m in EVENT_META):
            raise Http404("Unknown email type")

        recipient = (request.user.email or "").strip()
        if not recipient:
            return self._trigger_response(False, "Your account has no email address.")

        form = EmailTemplateForm(request.POST)
        if not form.is_valid():
            errors = []
            for field_errors in form.errors.values():
                errors.extend(field_errors)
            return self._trigger_response(
                False,
                errors[0] if errors else "Invalid template.",
            )

        sample = sample_context_for_event(event_type)
        subject, body, cta_label = render_subject_body(
            event_type,
            form.cleaned_data["subject"],
            form.cleaned_data["body"],
            sample,
        )
        if not subject.startswith("[TEST]"):
            subject = f"[TEST] {subject}"

        text_body, html_body = render_notification_email(
            body=body,
            cta_url=cta_url_for_event(event_type, sample),
            cta_label=cta_label,
            brand_name=sample.get("brand_name") or "mlamehticket",
            footer_note="This is a test email from Email Settings. Sample field values were used.",
        )
        sent = send_with_retries(
            subject,
            text_body,
            [recipient],
            html_body=html_body,
        )
        if not sent:
            return self._trigger_response(
                False,
                "Could not send. Check that an SMTP setting is active.",
            )
        return self._trigger_response(True, f"Test email sent to {recipient}.")


    @staticmethod
    def _trigger_response(ok: bool, message: str, status: int = 204):
        # Always return 2xx so HTMX still processes HX-Trigger for error toasts.
        response = HttpResponse(status=204 if ok else 200)
        response["HX-Trigger"] = json.dumps(
            {"emailTemplateTestResult": {"ok": ok, "message": message}}
        )
        return response
