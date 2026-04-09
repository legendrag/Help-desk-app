from django.contrib import admin

from core.models import Branch, Category, Department, EmailSetting, Role, RolePermission

admin.site.register(Branch)
admin.site.register(Department)
admin.site.register(Category)
admin.site.register(Role)
admin.site.register(RolePermission)
admin.site.register(EmailSetting)
