from urllib.parse import urlsplit

from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views import View

# We can reuse the built-in Django LoginView
from .forms import CustomAuthenticationForm, CustomPasswordChangeForm


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = CustomAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.headers.get("HX-Request"):
            return response

        redirect_to = response.get("Location") or self.get_success_url()
        user = form.get_user()
        if getattr(user, "requires_password_change", False):
            redirect_to = reverse("password_change")

        htmx_response = HttpResponse(status=204)
        htmx_response["HX-Redirect"] = redirect_to
        return htmx_response

    def get_template_names(self):
        if self.request.headers.get("HX-Request") and self.request.method == "POST":
            return ["accounts/login_form_partial.html"]
        return [self.template_name]


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


def logout_cancel_url(request):
    """Same-origin page that sent the user here, otherwise the ticket list."""
    fallback = reverse("tickets_list")
    referer = request.META.get("HTTP_REFERER") or ""
    if not url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return fallback

    parsed = urlsplit(referer)
    path = parsed.path or ""
    # A path of "//..." is protocol-relative and would leave this site.
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return fallback
    if path.rstrip("/") == reverse("logout").rstrip("/"):
        return fallback
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


class LogoutEntryView(View):
    """
    GET never logs the user out. Authenticated visitors confirm with a POST
    form; anonymous visitors go to login. POST stays on UserLogoutView.
    """

    http_method_names = ["get", "post", "options"]

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        return render(
            request,
            "accounts/logout_confirm.html",
            {"cancel_url": logout_cancel_url(request)},
        )

    def post(self, request, *args, **kwargs):
        return UserLogoutView.as_view()(request, *args, **kwargs)


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
