from django import forms
from .models import Announcement

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "content", "is_active", "expires_at", "target_branch", "target_department"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Announcement Title"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Message content..."}),
            "expires_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "target_branch": forms.Select(attrs={"class": "form-control"}),
            "target_department": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
