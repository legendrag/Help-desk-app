from django import forms
from django.urls import reverse_lazy
from .models import Ticket
from core.models import Branch, Department, Category

class CategorySelect(forms.Select):
    def __init__(self, categories_dict=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.categories_dict = categories_dict or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            val = getattr(value, 'value', value)
            if val in self.categories_dict:
                option['attrs']['data-priority'] = self.categories_dict[val]
        return option

class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "branch", "department", "category", "priority", "client_name", "client_phone"]
        widgets = {
            "priority": forms.HiddenInput(),
            "title": forms.TextInput(attrs={"minlength": "4", "required": "required", "placeholder": "Brief summary of the issue"}),
            "description": forms.Textarea(attrs={"rows": 4, "minlength": "5", "required": "required", "placeholder": "Describe the issue in detail..."}),
            "client_name": forms.TextInput(attrs={"minlength": "2", "required": "required", "placeholder": "Full name"}),
            "client_phone": forms.TextInput(attrs={
                "type": "tel",
                "pattern": r"^\+?1?\d{9,15}$",
                "required": "required",
                "placeholder": "e.g., +01020481863"
            }),
        }
        labels = {
            "client_name": "Name",
            "client_phone": "Phone Number",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} form-check-input".strip()
            elif not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} form-control".strip()

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
            qs = Category.objects.filter(department_id=department_id)
            self.fields["category"].queryset = qs
            cat_dict = {cat.id: cat.default_priority for cat in qs}
            self.fields["category"].widget = CategorySelect(categories_dict=cat_dict)
            self.fields["category"].widget.choices = self.fields["category"].choices
        else:
            self.fields["category"].queryset = Category.objects.none()

        self.fields["category"].widget.attrs.update({
            "class": "form-control",
            "onchange": "var p=this.options[this.selectedIndex].getAttribute('data-priority'); if(p) document.getElementById('id_priority').value = p;"
        })

        self.fields["department"].widget.attrs.update({
            "hx-get": reverse_lazy("ticket_category_options"),
            "hx-target": "#id_category",
            "hx-swap": "innerHTML",
            "hx-trigger": "change",
        })

        if user and user.user_type == "branch":
            self.fields["branch"].initial = user.branch
            self.fields["branch"].disabled = True

    def clean_client_name(self):
        name = self.cleaned_data.get("client_name")
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError("Name must be at least 2 characters long.")
        return name.strip()

    def clean_client_phone(self):
        import re
        phone = self.cleaned_data.get("client_phone")
        if not phone:
            raise forms.ValidationError("Phone number is required.")
        phone = phone.strip()
        pattern = r"^\+?1?\d{9,15}$"
        if not re.match(pattern, phone):
            raise forms.ValidationError("Enter a valid phone number (e.g. +01020481863).")
        return phone

    def clean_title(self):
        title = self.cleaned_data.get("title")
        if not title or len(title.strip()) < 4:
            raise forms.ValidationError("Title must be at least 4 characters long.")
        return title.strip()

    def clean_description(self):
        description = self.cleaned_data.get("description")
        if not description or len(description.strip()) < 5:
            raise forms.ValidationError("Description must be at least 5 characters long.")
        return description.strip()

class TicketUpdateForm(TicketCreateForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restore the visible select widget for priority during edit
        self.fields["priority"].widget = forms.Select(choices=Ticket._meta.get_field("priority").choices)
        self.fields["priority"].widget.attrs.update({"class": "form-control"})
