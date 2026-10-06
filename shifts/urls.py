from django.urls import path

from shifts import views

urlpatterns = [
    path("", views.shifts_home, name="shifts_home"),
    path("rota/", views.shifts_rota, name="shifts_rota"),
    path("rota/grid/", views.shifts_rota_grid, name="shifts_rota_grid"),
    path("cell/", views.shifts_cell, name="shifts_cell"),
    path("mine/", views.shifts_mine, name="shifts_mine"),
    path("available/", views.shifts_available, name="shifts_available"),
    path("types/", views.shifts_types, name="shifts_types"),
    path("types/add/", views.shifts_type_add, name="shifts_type_add"),
    path("types/<int:pk>/edit/", views.shifts_type_edit, name="shifts_type_edit"),
    path("types/<int:pk>/archive/", views.shifts_type_archive, name="shifts_type_archive"),
]
