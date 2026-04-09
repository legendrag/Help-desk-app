from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.urls import reverse_lazy
from django.shortcuts import render
from django.contrib import messages

# We can reuse the built-in Django LoginView
class UserLoginView(LoginView):
    template_name = "accounts/login.html"

class UserLogoutView(LogoutView):
    next_page = reverse_lazy("login")

class UserPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("tickets_list")
    
    def form_valid(self, form):
        messages.success(self.request, "Password changed successfully.")
        
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
