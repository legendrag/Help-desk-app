from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.utils.translation import gettext_noop
from core.management_views import BaseDeleteView
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm

class UserPermissionMixin(UserPassesTestMixin):
    def _target_is_superuser(self):
        user_id = getattr(self, 'kwargs', {}).get('pk')
        if not user_id:
            return False
        return User.objects.filter(pk=user_id, is_superuser=True).exists()

    def _target_outranks_editor(self):
        # Editing (or resetting the password of) someone with permissions the
        # editor lacks would let the editor take over that account.
        user_id = getattr(self, 'kwargs', {}).get('pk')
        if not user_id:
            return False
        target = User.objects.select_related('role').filter(pk=user_id).first()
        if target is None or target.role is None:
            return False
        return bool(target.role.permissions_beyond(self.request.user.role))

    def test_func(self):
        if not self.request.user.is_authenticated: return False
        role = getattr(self.request.user, 'role', None)

        if 'delete' in self.request.path or 'edit' in self.request.path:
            if self._target_is_superuser():
                return False

        if self.request.user.is_superuser: return True
        # If they don't even have settings access, deny entirely
        if not (role and role.can_access_settings): return False
        if ('delete' in self.request.path or 'edit' in self.request.path) and self._target_outranks_editor():
            return False
        
        if self.request.method == 'GET': return True
        if 'delete' in self.request.path:
            return role and role.can_delete_user
        if 'edit' in self.request.path:
            return role and role.can_update_user
        if 'add' in self.request.path: return role and role.can_create_user
        return False

class UserEditorMixin:
    """The user forms limit which roles the editor may hand out."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editor"] = self.request.user
        return kwargs


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
            # Keep English keys for template comparisons; translate on display via
            # |gettext. gettext_noop leaves the value untouched but makes it
            # visible to scripts/i18n.py extraction.
            _names = {
                "User": gettext_noop("User"),
            }
            context["model_name"] = _names.get(self.model.__name__, self.model.__name__)
        return context

# User Views
class UserCreateView(UserPermissionMixin, LoginRequiredMixin, UserEditorMixin, BaseManagementView, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = "accounts/management/form.html"
    partial_template_name = "accounts/management/form_partial.html"
    success_url = reverse_lazy('settings')

class UserUpdateView(UserPermissionMixin, LoginRequiredMixin, UserEditorMixin, BaseManagementView, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = "accounts/management/form.html"
    partial_template_name = "accounts/management/form_partial.html"
    success_url = reverse_lazy('settings')

class UserDeleteView(UserPermissionMixin, BaseDeleteView, DeleteView):
    # BaseDeleteView turns "still has tickets or messages" into a message, not a 500.
    model = User

class UserListView(UserPermissionMixin, LoginRequiredMixin, ListView):
    model = User
    template_name = "core/management/list_partial_v2.html"
    context_object_name = "object_list"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related("branch", "department", "role")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = gettext_noop("Users")
        context['create_url'] = reverse_lazy('user_create')
        context['edit_url_prefix'] = "/accounts/users/" # Matching the URL structure
        context['can_add'] = self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_create_user)
        context['can_edit'] = self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_update_user)
        context['can_delete'] = self.request.user.is_superuser or (self.request.user.role and self.request.user.role.can_delete_user)
        return context
