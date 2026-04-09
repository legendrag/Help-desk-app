from django.contrib import admin

from accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "user_type", "status", "branch", "department", "role")
    list_filter = ("user_type", "status", "branch", "department")
    search_fields = ("username", "email", "first_name", "last_name")
