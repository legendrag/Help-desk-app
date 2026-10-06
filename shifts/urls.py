from django.urls import path

from shifts import views

urlpatterns = [
    path("", views.shifts_home, name="shifts_home"),
    path("rota/", views.shifts_rota, name="shifts_rota"),
    path("rota/grid/", views.shifts_rota_grid, name="shifts_rota_grid"),
    path("rota/copy-week/", views.shifts_copy_week, name="shifts_copy_week"),
    path("rota/repeat-week/", views.shifts_repeat_week, name="shifts_repeat_week"),
    path("rota/auto-fill/", views.shifts_auto_fill, name="shifts_auto_fill"),
    path("calculator/rotation/", views.shifts_calc_rotation, name="shifts_calc_rotation"),
    path("calculator/", views.shifts_calculator, name="shifts_calculator"),
    path("calculator/hours/", views.shifts_calc_hours, name="shifts_calc_hours"),
    path("calculator/length/", views.shifts_calc_length, name="shifts_calc_length"),
    path("calculator/coverage/", views.shifts_calc_coverage, name="shifts_calc_coverage"),
    path("cell/", views.shifts_cell, name="shifts_cell"),
    path("mine/", views.shifts_mine, name="shifts_mine"),
    path("team/", views.shifts_team, name="shifts_team"),
    path("mine/<int:pk>/hours/", views.shifts_mine_hours, name="shifts_mine_hours"),
    path("mine/<int:pk>/check-in/", views.shifts_check_in, name="shifts_check_in"),
    path("available/", views.shifts_available, name="shifts_available"),
    path("available/board/", views.shifts_available_board, name="shifts_available_board"),
    path("types/", views.shifts_types, name="shifts_types"),
    path("types/add/", views.shifts_type_add, name="shifts_type_add"),
    path("types/<int:pk>/edit/", views.shifts_type_edit, name="shifts_type_edit"),
    path("types/<int:pk>/archive/", views.shifts_type_archive, name="shifts_type_archive"),
]
