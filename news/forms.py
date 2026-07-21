from django import forms
from django.utils import timezone
from django.utils.timezone import localtime

from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "content", "is_active", "expires_at", "target_branch"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Announcement Title"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Message content..."}),
            "expires_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                    "step": "60",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "target_branch": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # iOS datetime-local may include seconds; accept common variants
        self.fields["expires_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]
        expires_at = getattr(self.instance, "expires_at", None)
        if expires_at:
            # datetime-local expects a naive local wall-clock value
            local_dt = localtime(expires_at) if timezone.is_aware(expires_at) else expires_at
            self.initial["expires_at"] = local_dt.strftime("%Y-%m-%dT%H:%M")
