from django.urls import path

from .views import notifications_list, mark_notifications_read

urlpatterns = [
    path("api/", notifications_list, name="notifications_list"),
    path("mark-read/", mark_notifications_read, name="notifications_mark_read"),
]
