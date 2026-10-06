from django.urls import path

from shifts import views

urlpatterns = [
    path("", views.shifts_home, name="shifts_home"),
    path("rota/", views.shifts_rota, name="shifts_rota"),
    path("mine/", views.shifts_mine, name="shifts_mine"),
    path("available/", views.shifts_available, name="shifts_available"),
]
