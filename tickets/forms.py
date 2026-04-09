from django import forms
from django.urls import reverse_lazy
from .models import Ticket
from core.models import Branch, Department, Category

class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "branch", "department", "category", "priority"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        for field_name in ("branch", "department", "category"):
            field = self.fields.get(field_name)
            if field and hasattr(field, "empty_label"):
                field.empty_label = ""

        department_id = (
            self.data.get("department")
            or self.initial.get("department")
            or (self.instance.department_id if self.instance and self.instance.pk else None)
        )
        if department_id:
            self.fields["category"].queryset = Category.objects.filter(department_id=department_id)
        else:
            self.fields["category"].queryset = Category.objects.none()

        self.fields["department"].widget.attrs.update({
            "hx-get": reverse_lazy("ticket_category_options"),
            "hx-target": "#id_category",
            "hx-swap": "innerHTML",
            "hx-trigger": "change",
        })

        if user and user.user_type == "branch":
            self.fields["branch"].initial = user.branch
            self.fields["branch"].widget = forms.HiddenInput()
