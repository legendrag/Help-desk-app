from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.urls import reverse_lazy
from django.shortcuts import render
from django.contrib import messages

# We can reuse the built-in Django LoginView
from .forms import CustomAuthenticationForm

class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = CustomAuthenticationForm

class UserLogoutView(LogoutView):
    next_page = reverse_lazy("login")

class UserPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("tickets_list")
    
    def form_valid(self, form):
        messages.success(self.request, "Password changed successfully.")
        
        # Clear the requires_password_change flag if it's set
        if getattr(self.request.user, 'requires_password_change', False):
            self.request.user.requires_password_change = False
            self.request.user.save(update_fields=['requires_password_change'])
        
        if self.request.headers.get('HX-Request'):
            from django.http import HttpResponse
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'closeModal'
            return response
            
        return super().form_valid(form)

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ["accounts/password_change_partial.html"]
        return [self.template_name]
