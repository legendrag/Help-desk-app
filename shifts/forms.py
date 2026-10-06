import re

from django import forms
from django.utils.translation import gettext_lazy as _

from shifts.models import ShiftType

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ShiftTypeForm(forms.ModelForm):
    class Meta:
        model = ShiftType
        fields = ["department", "name", "start_time", "end_time", "colour", "archived"]
        widgets = {
            "start_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "end_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields.pop("archived")

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError(_("Shift type name must be at least 2 characters long."))
        return name.strip()

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and start == end:
            self.add_error("end_time", _("Start and end must differ."))
        colour = cleaned.get("colour") or ""
        if colour and not _HEX.match(colour):
            self.add_error("colour", _("Colour must be a 6-digit hex value."))
        return cleaned
