from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _

# We can reuse the built-in Django LoginView
from .forms import CustomAuthenticationForm, CustomPasswordChangeForm


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = CustomAuthenticationForm
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("login")

    def dispatch(self, request, *args, **kwargs):
        # Capture user before LogoutView clears the session.
        self._logout_user = request.user if request.user.is_authenticated else None
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # Belt-and-suspenders when JS unsubscribe did not run (no-JS / failed fetch).
        # Clears every device for this account; remaining open sessions re-subscribe
        # on their next authenticated page load via initWebPush().
        user = getattr(self, "_logout_user", None)
        if user is not None:
            try:
                from notifications.webpush_cleanup import clear_user_webpush_subscriptions

                clear_user_webpush_subscriptions(user)
            except Exception:
                pass
        return response


class UserPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy("tickets_list")

    def form_valid(self, form):
        # Save the form which updates the password
        response = super().form_valid(form)

        messages.success(
            self.request,
            _("Password changed successfully. Please log in again with your new password."),
        )

        # Clear the requires_password_change flag if it's set
        if getattr(self.request.user, "requires_password_change", False):
            self.request.user.requires_password_change = False
            self.request.user.save(update_fields=["requires_password_change"])

        # Password change forces logout — drop all push endpoints for this user.
        try:
            from notifications.webpush_cleanup import clear_user_webpush_subscriptions

            clear_user_webpush_subscriptions(self.request.user)
        except Exception:
            pass

        # Log the user out for security
        from django.contrib.auth import logout

        logout(self.request)

        if self.request.META.get("HTTP_HX_REQUEST"):
            from django.http import HttpResponse
            from django.urls import reverse

            htmx_response = HttpResponse(status=204)
            htmx_response["HX-Redirect"] = reverse("login")
            return htmx_response

        return response

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["accounts/password_change_partial.html"]
        return [self.template_name]
