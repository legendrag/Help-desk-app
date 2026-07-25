import re

from django import forms
from .models import (
    Branch,
    Department,
    Category,
    Role,
    EmailAppearance,
    EmailSetting,
    EmailTemplate,
)

def _style_fields(form):
    for name, field in form.fields.items():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} form-check-input".strip()
        elif not isinstance(field.widget, forms.HiddenInput):
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} form-control".strip()

class BranchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)

    class Meta:
        model = Branch
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'minlength': '2', 'placeholder': 'e.g., Main Branch'}),
            'code': forms.TextInput(attrs={'minlength': '1', 'placeholder': 'e.g., MBR'}),
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)

    class Meta:
        model = Department
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'minlength': '2', 'placeholder': 'e.g., IT Support'}),
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
        _style_fields(self)
        for field in self.fields.values():
            if hasattr(field, 'empty_label'):
                field.empty_label = ''

    class Meta:
        model = Category
        fields = ['department', 'name', 'default_priority']
        widgets = {
            'name': forms.TextInput(attrs={'minlength': '2', 'placeholder': 'e.g., Hardware Issue'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError("Category name must be at least 2 characters long.")
        return name.strip()

class RoleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)

    class Meta:

        widgets = {
            'name': forms.TextInput(attrs={'minlength': '2', 'placeholder': 'e.g., Support Agent'}),
            'can_create_ticket': forms.CheckboxInput(),
            'can_update_ticket': forms.CheckboxInput(),
            'can_pick_ticket': forms.CheckboxInput(),
            'can_update_status': forms.CheckboxInput(),
            'can_update_closed_ticket': forms.CheckboxInput(),
            'can_send_message': forms.CheckboxInput(),
            'can_edit_message': forms.CheckboxInput(),
            'can_delete_message': forms.CheckboxInput(),
            'can_access_dashboard': forms.CheckboxInput(),
            'can_view_leaderboard': forms.CheckboxInput(),
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
            'can_manage_news': forms.CheckboxInput(),
            'can_access_kb': forms.CheckboxInput(),
            'can_manage_kb': forms.CheckboxInput(),
            'can_manage_maintenance': forms.CheckboxInput(),
        }
        model = Role
        fields = [
            'name', 'description', 
            
            # Ticket Permissions
            'can_create_ticket', 'can_update_ticket', 'can_pick_ticket', 'can_update_status', 
            'can_update_closed_ticket', 'can_send_message', 'can_edit_message', 
            'can_delete_message', 'can_access_dashboard', 'can_view_leaderboard', 'can_access_settings',
            'can_manage_news',

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
            'can_manage_email',
            'can_manage_news',
            'can_access_kb',
            'can_manage_kb',
            'can_manage_maintenance',
        ]

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError("Role name must be at least 2 characters long.")
        return name.strip()

class EmailSettingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)

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
            'notify_ticket_status', 'notify_ticket_update', 'notify_announcement',
        ]
        widgets = {
            'smtp_host': forms.TextInput(attrs={'placeholder': 'e.g., smtp.gmail.com'}),
            'smtp_port': forms.NumberInput(attrs={'placeholder': 'e.g., 587'}),
            'smtp_email': forms.EmailInput(attrs={'placeholder': 'sender@example.com'}),
            'smtp_password': forms.PasswordInput(render_value=True, attrs={'placeholder': '••••••••'}),
            'from_name': forms.TextInput(attrs={'placeholder': 'e.g., mlamehticket Support'}),
            'from_email': forms.EmailInput(attrs={'placeholder': 'noreply@example.com'}),
        }


class EmailAppearanceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)
        self.fields["brand_name"].label = "Name shown at the top of emails"
        self.fields["accent_color"].label = "Accent color"
        self.fields["footer_note"].label = "Footer text at the bottom"

    def clean_accent_color(self):
        color = (self.cleaned_data.get("accent_color") or "").strip()
        if not re.match(r"^#[0-9A-Fa-f]{6}$", color):
            raise forms.ValidationError("Enter a valid hex color like #4f46e5.")
        return color.lower()

    def clean_brand_name(self):
        name = (self.cleaned_data.get("brand_name") or "").strip()
        if len(name) < 1:
            raise forms.ValidationError("Brand name is required.")
        return name

    class Meta:
        model = EmailAppearance
        fields = ["brand_name", "accent_color", "footer_note"]
        widgets = {
            "brand_name": forms.TextInput(
                attrs={"placeholder": "e.g., mlamehticket", "data-email-preview": "brand"}
            ),
            "accent_color": forms.TextInput(
                attrs={
                    "placeholder": "#4f46e5",
                    "type": "text",
                    "data-email-preview": "accent",
                    "spellcheck": "false",
                }
            ),
            "footer_note": forms.Textarea(
                attrs={"rows": 3, "data-email-preview": "footer"}
            ),
        }


class EmailTemplateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)
        self.fields["subject"].label = "Email subject (inbox line)"
        self.fields["headline"].label = "Big title inside the email"
        self.fields["intro"].label = "Opening sentence"
        self.fields["message_title"].label = "Label above the message"
        self.fields["cta_label"].label = "Button text"
        self.fields["is_active"].label = "Use this custom wording"
        self.fields["is_active"].help_text = (
            "Turn off to fall back to the built-in default wording for this email."
        )
        for name in ("subject", "headline", "intro", "message_title", "cta_label"):
            self.fields[name].widget.attrs["data-email-field"] = name
            self.fields[name].widget.attrs["data-email-insert-target"] = "1"

    def _reject_template_tags(self, value: str, label: str) -> str:
        if value and ("{%" in value or "%}" in value):
            raise forms.ValidationError(
                f"{label} can include dynamic fields via the buttons above, "
                "but not advanced template tags."
            )
        return value

    def clean_subject(self):
        subject = (self.cleaned_data.get("subject") or "").strip()
        if not subject:
            raise forms.ValidationError("Subject is required.")
        return self._reject_template_tags(subject, "Subject")

    def clean_headline(self):
        headline = (self.cleaned_data.get("headline") or "").strip()
        if not headline:
            raise forms.ValidationError("Headline is required.")
        return self._reject_template_tags(headline, "Headline")

    def clean_intro(self):
        return self._reject_template_tags(self.cleaned_data.get("intro") or "", "Intro")

    def clean_message_title(self):
        return self._reject_template_tags(
            self.cleaned_data.get("message_title") or "", "Message title"
        )

    def clean_cta_label(self):
        return self._reject_template_tags(self.cleaned_data.get("cta_label") or "", "CTA label")

    class Meta:
        model = EmailTemplate
        fields = [
            "subject",
            "headline",
            "intro",
            "message_title",
            "cta_label",
            "is_active",
        ]
        widgets = {
            "subject": forms.TextInput(
                attrs={"placeholder": "New ticket #TK-1042: Printer offline"}
            ),
            "headline": forms.TextInput(attrs={"placeholder": "New ticket #TK-1042"}),
            "intro": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Sam Rivera submitted a new request for IT Support.",
                }
            ),
            "message_title": forms.TextInput(attrs={"placeholder": "Request"}),
            "cta_label": forms.TextInput(attrs={"placeholder": "View ticket"}),
        }

