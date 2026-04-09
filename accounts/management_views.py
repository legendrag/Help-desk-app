from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import HttpResponse
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm

class UserPermissionMixin(UserPassesTestMixin):
    def _target_is_superuser(self):
        user_id = getattr(self, 'kwargs', {}).get('pk')
        if not user_id:
            return False
        return User.objects.filter(pk=user_id, is_superuser=True).exists()

    def test_func(self):
        if not self.request.user.is_authenticated: return False
        role = getattr(self.request.user, 'role', None)

        if 'delete' in self.request.path or 'edit' in self.request.path:
            if self._target_is_superuser():
                return False

        if self.request.user.is_superuser: return True
        # If they don't even have settings access, deny entirely
        if not (role and role.can_access_settings): return False
        
        if self.request.method == 'GET': return True
        if 'delete' in self.request.path:
            return role and role.can_delete_user
        if 'edit' in self.request.path:
            return role and role.can_update_user
        if 'add' in self.request.path: return role and role.can_create_user
        return False

class BaseManagementView:
    def form_valid(self, form):
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

# User Views
class UserCreateView(UserPermissionMixin, LoginRequiredMixin, BaseManagementView, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = "accounts/management/form.html"
    partial_template_name = "accounts/management/form_partial.html"
    success_url = reverse_lazy('settings')

class UserUpdateView(UserPermissionMixin, LoginRequiredMixin, BaseManagementView, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = "accounts/management/form.html"
    partial_template_name = "accounts/management/form_partial.html"
    success_url = reverse_lazy('settings')

class UserDeleteView(UserPermissionMixin, LoginRequiredMixin, DeleteView):
    model = User
    template_name = "core/management/delete_confirm.html"
    success_url = reverse_lazy('settings')

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if self.request.headers.get('HX-Request'):
            resp = HttpResponse(status=204)
            resp['HX-Trigger'] = 'closeModal,refreshSettings'
            return resp
        return response

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ["core/management/delete_confirm_partial.html"]
        return [self.template_name]

class UserListView(UserPermissionMixin, LoginRequiredMixin, ListView):
    model = User
    template_name = "core/management/list_partial_v2.html"
    context_object_name = "object_list"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = "Users"
        context['create_url'] = reverse_lazy('user_create')
        context['edit_url_prefix'] = "/accounts/users/" # Matching the URL structure
        context['can_add'] = self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_create_user)
        context['can_edit'] = self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_update_user)
        context['can_delete'] = self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_delete_user)
        return context

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return [self.template_name]
        return ["accounts/management/list.html"]
