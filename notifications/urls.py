from django.urls import path

from .views import (
    notifications_list,
    mark_notifications_read,
    mark_notification_read,
    delete_notification,
    clear_read_notifications,
)

urlpatterns = [
    path("api/", notifications_list, name="notifications_list"),
    path("mark-read/", mark_notifications_read, name="notifications_mark_read"),
    path("mark-read/<int:notification_id>/", mark_notification_read, name="notification_mark_read"),
    path("delete/<int:notification_id>/", delete_notification, name="notification_delete"),
    path("clear-read/", clear_read_notifications, name="notifications_clear_read"),
]
