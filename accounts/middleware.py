from django.shortcuts import redirect
from django.urls import reverse

class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, 'requires_password_change', False):
            # Paths that are allowed to be accessed without changing password
            allowed_paths = [
                reverse('password_change'),
                reverse('logout'),
                # Add any static/media/admin URLs here if needed, 
                # but static and media are usually handled before this middleware or not by Django directly.
            ]
            
            # Allow static files or django admin if necessary
            if not request.path.startswith('/static/') and not request.path.startswith('/media/') and not request.path.startswith('/admin/'):
                if request.path not in allowed_paths:
                    return redirect('password_change')
                    
        response = self.get_response(request)
        return response


class UserLanguageMiddleware:
    """Use the signed-in user's saved language instead of the browser's cookie.

    LocaleMiddleware runs before authentication, so it can only read the
    cookie. This runs after, switches to ``user.language``, and rewrites the
    cookie to match (the pre-paint RTL script and the login page read it).
    A user who never chose a language adopts the one their browser is using.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from django.utils import translation

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            supported = {code for code, _name in settings.LANGUAGES}
            if user.language not in supported:
                user.language = translation.get_language_from_request(request)
                if user.language not in supported:
                    user.language = settings.LANGUAGE_CODE
                get_user_model().objects.filter(pk=user.pk).update(language=user.language)
            translation.activate(user.language)
            request.LANGUAGE_CODE = user.language

        response = self.get_response(request)

        # Re-read: the request may have logged someone in or changed the language.
        user = getattr(request, "user", None)
        language = getattr(user, "language", "") if user is not None and user.is_authenticated else ""
        if language and request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME) != language:
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                language,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                domain=settings.LANGUAGE_COOKIE_DOMAIN,
                secure=settings.LANGUAGE_COOKIE_SECURE,
                httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
                samesite=settings.LANGUAGE_COOKIE_SAMESITE,
            )
        return response
