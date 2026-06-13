from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.core.cache import cache
from .models import User

class CustomAuthenticationForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        
        if username:
            cache_key = f'login_attempts_{username}'
            attempts = cache.get(cache_key, 0)
            
            # Rate limiting configuration: 5 attempts / 5 minutes
            MAX_ATTEMPTS = 5
            TIMEOUT = 300  # 5 minutes in seconds
            
            if attempts >= MAX_ATTEMPTS:
                raise forms.ValidationError(
                    "Too many failed login attempts. Please try again in 5 minutes.",
                    code='too_many_attempts',
                )

            try:
                cleaned_data = super().clean()
                # On successful login, clear the cache
                cache.delete(cache_key)
                return cleaned_data
            except forms.ValidationError as e:
                # Increment attempts only on a failed auth error (not other random validation errors)
                if e.code == 'invalid_login':
                    attempts += 1
                    cache.set(cache_key, attempts, TIMEOUT)
                raise e
        else:
            return super().clean()


class CustomUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if hasattr(field, 'empty_label'):
                field.empty_label = ''
        for field_name in ("branch", "department"):
            if field_name in self.fields:
                self.fields[field_name].required = False

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if not username:
            return username
        username = username.strip().lower()
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip()
        return email or None

    def validate_unique(self):
        exclude = set(self._get_validation_exclusions())
        if not self.cleaned_data.get("email"):
            exclude.add("email")
        try:
            self.instance.validate_unique(exclude=list(exclude))
        except forms.ValidationError as e:
            self._update_errors(e)

    def clean(self):
        cleaned = super().clean()
        if cleaned is None:
            cleaned = self.cleaned_data
            
        user_type = cleaned.get("user_type")
        branch = cleaned.get("branch")
        department = cleaned.get("department")

        if getattr(self.instance, 'is_superuser', False):
            return cleaned

        if user_type == User.UserType.BRANCH:
            if not branch:
                self.add_error("branch", "Branch is required for this user type.")
            cleaned["department"] = None
        elif user_type == User.UserType.SUPPORT:
            if not department:
                self.add_error("department", "Department is required for this user type.")
            cleaned["branch"] = None

        return cleaned

    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name',
            'phone', 'user_type', 'status', 'branch',
            'department', 'role', 'requires_password_change'
        )


class CustomUserChangeForm(UserChangeForm):
    password1 = forms.CharField(
        label="New password",
        required=False,
        widget=forms.PasswordInput(attrs={'minlength': 4}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        required=False,
        widget=forms.PasswordInput(attrs={'minlength': 4}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if hasattr(field, 'empty_label'):
                field.empty_label = ''
        for field_name in ("branch", "department"):
            if field_name in self.fields:
                self.fields[field_name].required = False

        if "password" in self.fields:
            self.fields.pop("password")

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if not username:
            return username
        username = username.strip().lower()
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip()
        return email or None

    def validate_unique(self):
        exclude = set(self._get_validation_exclusions())
        if not self.cleaned_data.get("email"):
            exclude.add("email")
        try:
            self.instance.validate_unique(exclude=list(exclude))
        except forms.ValidationError as e:
            self._update_errors(e)

    def clean(self):
        cleaned = super().clean()
        if cleaned is None:
            cleaned = self.cleaned_data
            
        user_type = cleaned.get("user_type")
        branch = cleaned.get("branch")
        department = cleaned.get("department")

        if getattr(self.instance, 'is_superuser', False):
            return cleaned

        if user_type == User.UserType.BRANCH:
            if not branch:
                self.add_error("branch", "Branch is required for this user type.")
            cleaned["department"] = None
        elif user_type == User.UserType.SUPPORT:
            if not department:
                self.add_error("department", "Department is required for this user type.")
            cleaned["branch"] = None

        return cleaned

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError("Passwords do not match.")
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            try:
                validate_password(p2, self.instance)
            except ValidationError as e:
                self.add_error("password1", e)
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user

    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name',
            'phone', 'user_type', 'status', 'branch',
            'department', 'role', 'requires_password_change', 'password1', 'password2'
        )
