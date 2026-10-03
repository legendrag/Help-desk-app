import os

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.models import User

from .models import Article, Category
from .sanitize import sanitize_article_html


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        for f in result:
            if not f:
                continue
            name = getattr(f, "name", "") or ""
            _, ext = os.path.splitext(name.lower())
            allowed = [e.lower() for e in getattr(settings, "ALLOWED_ATTACHMENT_EXTENSIONS", [])]
            if allowed and ext not in allowed:
                raise ValidationError(
                    _("Attachment type '%(ext)s' is not allowed. Allowed: %(allowed)s")
                    % {"ext": ext or _("(none)"), "allowed": ", ".join(allowed)}
                )
            max_size = getattr(settings, "MAX_ATTACHMENT_SIZE", None)
            size = getattr(f, "size", None)
            if max_size and size is not None and size > max_size:
                raise ValidationError(
                    _("Attachment is too large (%(size)s bytes). Maximum is %(max_size)s bytes.")
                    % {"size": size, "max_size": max_size}
                )
        return result

class ArticleForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        help_text=_("Select one or more pictures or files to attach."),
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.docx,.xlsx,.jpg,.jpeg,.png,image/*,application/pdf',
            'multiple': True
        })
    )

    class Meta:
        model = Article
        fields = ["title", "category", "visibility", "related_ticket", "content"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "required": True,
                "placeholder": _("e.g. How to reset a branch password"),
            }),
            "category": forms.Select(attrs={"class": "form-control"}),
            "visibility": forms.Select(attrs={"class": "form-control"}),
            "related_ticket": forms.HiddenInput(attrs={"id": "id_related_ticket"}),
            "content": forms.Textarea(attrs={
                "class": "form-control tinymce-editor",
                "rows": 10,
            }),
        }

    def __init__(self, *args, author=None, editor=None, **kwargs):
        self.author = author
        self.editor = editor or author
        super().__init__(*args, **kwargs)
        if hasattr(self.fields['category'], 'empty_label'):
            self.fields['category'].empty_label = _("No Category")
        if not getattr(self.author, "department_id", None):
            self.fields["visibility"].choices = [
                (value, label)
                for value, label in self.fields["visibility"].choices
                if value != Article.Visibility.DEPARTMENT
            ]

    def clean_content(self):
        return sanitize_article_html(self.cleaned_data.get("content") or "")

    def clean_visibility(self):
        visibility = self.cleaned_data.get("visibility")
        if (
            visibility == Article.Visibility.DEPARTMENT
            and not getattr(self.author, "department_id", None)
        ):
            raise ValidationError(_("My department is unavailable without a department."))
        return visibility

    def clean_related_ticket(self):
        ticket = self.cleaned_data.get("related_ticket")
        if not ticket:
            return ticket
        if self.instance and self.instance.related_ticket_id == ticket.id:
            return ticket
        editor = self.editor
        if editor and editor.is_superuser:
            return ticket
        if (
            editor
            and editor.user_type == User.UserType.SUPPORT
            and editor.department_id
            and ticket.department_id == editor.department_id
        ):
            return ticket
        if (
            editor
            and editor.user_type == User.UserType.BRANCH
            and editor.branch_id
            and ticket.branch_id == editor.branch_id
        ):
            return ticket
        raise ValidationError(_("You cannot relate a ticket outside your organization."))

class KBCategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'icon': forms.Select(attrs={'class': 'form-control icon-select'}),
        }
