from django.contrib import admin

from .models import ShiftAssignment, ShiftType


@admin.register(ShiftType)
class ShiftTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "start_time", "end_time", "is_night", "archived")
    list_filter = ("archived", "is_night", "department")


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "shift_type", "checked_in_at")
    list_filter = ("date", "shift_type__department")
