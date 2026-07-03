from django.urls import path
from .management_views import (
    BranchCreateView, BranchUpdateView, BranchDeleteView,
    DepartmentCreateView, DepartmentUpdateView, DepartmentDeleteView,
    CategoryCreateView, CategoryUpdateView, CategoryDeleteView,
    RoleCreateView, RoleUpdateView, RoleDeleteView,
    EmailSettingCreateView, EmailSettingUpdateView, EmailSettingDeleteView,
    BranchListView, DepartmentListView, CategoryListView, RoleListView, EmailSettingListView
)
from .maintenance_views import (
    MaintenanceView, BackupDatabaseView, BackupMediaView,
    CleanupTicketsView
)

urlpatterns = [
    path('branches/add/', BranchCreateView.as_view(), name='branch_create'),
    path('branches/<int:pk>/edit/', BranchUpdateView.as_view(), name='branch_update'),
    
    path('departments/add/', DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', DepartmentUpdateView.as_view(), name='department_update'),
    
    path('categories/add/', CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', CategoryUpdateView.as_view(), name='category_update'),
    
    path('roles/add/', RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/edit/', RoleUpdateView.as_view(), name='role_update'),
    
    path('email-settings/add/', EmailSettingCreateView.as_view(), name='email_setting_create'),
    path('email-settings/<int:pk>/edit/', EmailSettingUpdateView.as_view(), name='email_setting_update'),
    path('branches/<int:pk>/delete/', BranchDeleteView.as_view(), name='branch_delete'),
    
    path('departments/<int:pk>/delete/', DepartmentDeleteView.as_view(), name='department_delete'),
    
    path('categories/<int:pk>/delete/', CategoryDeleteView.as_view(), name='category_delete'),
    
    path('roles/<int:pk>/delete/', RoleDeleteView.as_view(), name='role_delete'),
    
    path('email-settings/<int:pk>/delete/', EmailSettingDeleteView.as_view(), name='email_setting_delete'),

    # Lists
    path('branches/', BranchListView.as_view(), name='branch_list'),
    path('departments/', DepartmentListView.as_view(), name='department_list'),
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('roles/', RoleListView.as_view(), name='role_list'),
    path('email-settings/', EmailSettingListView.as_view(), name='email_setting_list'),

    # Maintenance
    path('maintenance/', MaintenanceView.as_view(), name='maintenance'),
    path('maintenance/backup/db/', BackupDatabaseView.as_view(), name='backup_db'),
    path('maintenance/backup/media/', BackupMediaView.as_view(), name='backup_media'),
    path('maintenance/cleanup/tickets/', CleanupTicketsView.as_view(), name='cleanup_tickets'),
]
