from django import forms
from .models import Article, ArticleAttachment

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
        return result

class ArticleForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        help_text="Select one or more pictures or files to attach.",
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,application/pdf,.doc,.docx',
            'multiple': True
        })
    )

    class Meta:
        model = Article
        fields = ["title", "category", "content"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "required": True}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={
                "class": "form-control tinymce-editor", 
                "rows": 10
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self.fields['category'], 'empty_label'):
            self.fields['category'].empty_label = "No Category"
