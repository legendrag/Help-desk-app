from django.urls import path
from django.http import JsonResponse
from .template_views import UserLoginView, UserLogoutView, UserPasswordChangeView
from .management_views import UserListView, UserCreateView, UserUpdateView, UserDeleteView


def auth_check(request):
    return JsonResponse({'authenticated': request.user.is_authenticated})

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("password-change/", UserPasswordChangeView.as_view(), name="password_change"),
    
    # Management
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/add/", UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/delete/", UserDeleteView.as_view(), name="user_delete"),
    path("auth-check/", auth_check, name="auth_check"),
]
