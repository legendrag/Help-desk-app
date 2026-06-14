from django import forms
from .models import Branch, Department, Category, Role, EmailSetting

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'minlength': '2'}),
            'code': forms.TextInput(attrs={'minlength': '1'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError("Branch name must be at least 2 characters long.")
        return name.strip()

    def clean_code(self):
        import re
        code = self.cleaned_data.get('code')
        if not code or not code.strip():
            raise forms.ValidationError("Branch code is required.")
        code = code.strip().upper()
        if not re.match(r'^[A-Z0-9_-]+$', code):
            raise forms.ValidationError("Code may only contain letters, numbers, hyphens, and underscores.")
        return code

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'minlength': '2'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError("Department name must be at least 2 characters long.")
        name = name.strip()
        qs = Department.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A department with this name already exists.")
        return name

class CategoryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if hasattr(field, 'empty_label'):
                field.empty_label = ''

    class Meta:
        model = Category
        fields = ['department', 'name', 'default_priority']
        widgets = {
            'name': forms.TextInput(attrs={'minlength': '2'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError("Category name must be at least 2 characters long.")
        return name.strip()

class RoleForm(forms.ModelForm):
    class Meta:

        widgets = {
            'name': forms.TextInput(attrs={'minlength': '2'}),
            'can_create_ticket': forms.CheckboxInput(),
            'can_update_ticket': forms.CheckboxInput(),
            'can_pick_ticket': forms.CheckboxInput(),
            'can_update_status': forms.CheckboxInput(),
            'can_update_closed_ticket': forms.CheckboxInput(),
            'can_send_message': forms.CheckboxInput(),
            'can_edit_message': forms.CheckboxInput(),
            'can_delete_message': forms.CheckboxInput(),
            'can_access_dashboard': forms.CheckboxInput(),
            'can_access_settings': forms.CheckboxInput(),
            'can_create_user': forms.CheckboxInput(),
            'can_update_user': forms.CheckboxInput(),
            'can_delete_user': forms.CheckboxInput(),
            'can_create_branch': forms.CheckboxInput(),
            'can_update_branch': forms.CheckboxInput(),
            'can_delete_branch': forms.CheckboxInput(),
            'can_create_department': forms.CheckboxInput(),
            'can_update_department': forms.CheckboxInput(),
            'can_delete_department': forms.CheckboxInput(),
            'can_create_category': forms.CheckboxInput(),
            'can_update_category': forms.CheckboxInput(),
            'can_delete_category': forms.CheckboxInput(),
            'can_create_role': forms.CheckboxInput(),
            'can_update_role': forms.CheckboxInput(),
            'can_delete_role': forms.CheckboxInput(),
            'can_manage_email': forms.CheckboxInput(),
        }
        model = Role
        fields = [
            'name', 'description', 
            
            # Ticket Permissions
            'can_create_ticket', 'can_update_ticket', 'can_pick_ticket', 'can_update_status', 
            'can_update_closed_ticket', 'can_send_message', 'can_edit_message', 
            'can_delete_message', 'can_access_dashboard', 'can_access_settings',

            # Settings Permissions (Users)
            'can_create_user', 'can_update_user', 'can_delete_user',

            # Settings Permissions (Branches)
            'can_create_branch', 'can_update_branch', 'can_delete_branch',

            # Settings Permissions (Departments)
            'can_create_department', 'can_update_department', 'can_delete_department',

            # Settings Permissions (Categories)
            'can_create_category', 'can_update_category', 'can_delete_category',

            # Settings Permissions (Roles)
            'can_create_role', 'can_update_role', 'can_delete_role',

            # Settings Permissions (Email)
            'can_manage_email'
        ]

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError("Role name must be at least 2 characters long.")
        return name.strip()

class EmailSettingForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        is_active = cleaned.get('is_active')
        if is_active:
            qs = EmailSetting.objects.filter(is_active=True)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('is_active', 'Another email setting is already active. Disable it before activating this one.')
        return cleaned

    class Meta:
        model = EmailSetting
        fields = [
            'smtp_host', 'smtp_port', 'smtp_email', 'smtp_password', 
            'encryption', 'from_name', 'from_email', 'is_active',
            'notify_new_ticket', 'notify_ticket_picked', 'notify_ticket_message',
            'notify_ticket_status', 'notify_ticket_update'
        ]
        widgets = {
            'smtp_password': forms.PasswordInput(render_value=True),
        }

