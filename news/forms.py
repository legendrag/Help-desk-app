from datetime import datetime, time

from django import forms
from django.utils import timezone
from django.utils.timezone import localtime, make_aware

from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    """Split expiry into date + time — iOS Safari renders datetime-local poorly."""

    expires_date = forms.DateField(
        required=False,
        label="Expires on",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
                "autocomplete": "off",
            },
            format="%Y-%m-%d",
        ),
        input_formats=["%Y-%m-%d"],
    )
    expires_time = forms.TimeField(
        required=False,
        label="Expires at",
        widget=forms.TimeInput(
            attrs={
                "class": "form-control",
                "type": "time",
                "step": "60",
                "autocomplete": "off",
            },
            format="%H:%M",
        ),
        input_formats=["%H:%M", "%H:%M:%S"],
    )

    class Meta:
        model = Announcement
        fields = ["title", "content", "is_active", "target_branch"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Announcement Title"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Message content..."}),
            "target_branch": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        expires_at = getattr(self.instance, "expires_at", None)
        if expires_at:
            local_dt = localtime(expires_at) if timezone.is_aware(expires_at) else expires_at
            self.fields["expires_date"].initial = local_dt.date()
            self.fields["expires_time"].initial = local_dt.time().replace(second=0, microsecond=0)

    def clean(self):
        cleaned = super().clean()
        expires_date = cleaned.get("expires_date")
        expires_time = cleaned.get("expires_time")

        if expires_time and not expires_date:
            self.add_error("expires_date", "Enter a date when setting an expiration time.")
            return cleaned

        if expires_date:
            combined = datetime.combine(expires_date, expires_time or time(23, 59))
            if timezone.is_naive(combined):
                combined = make_aware(combined, timezone.get_current_timezone())
            cleaned["expires_at"] = combined
        else:
            cleaned["expires_at"] = None

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.expires_at = self.cleaned_data.get("expires_at")
        if commit:
            instance.save()
            self.save_m2m()
        return instance
