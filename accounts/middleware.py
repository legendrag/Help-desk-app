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
