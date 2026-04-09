from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import HttpResponse
from .models import Branch, Department, Category, Role, EmailSetting
from .forms import BranchForm, DepartmentForm, CategoryForm, RoleForm, EmailSettingForm

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
        context.update({
            'model_name': 'Email Settings',
            'create_url': reverse_lazy('email_setting_create'),
            'edit_url_prefix': '/core/email-settings/',
            'can_add': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_manage_email),
            'can_edit': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_manage_email),
            'can_delete': self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_manage_email),
        })
        return context
