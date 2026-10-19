from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm, PasswordChangeForm
from django.utils.translation import gettext_lazy as _
from core.utils import normalize_digits

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)
from .models import User

def _style_fields(form):
    for name, field in form.fields.items():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} form-check-input".strip()
        elif not isinstance(field.widget, forms.HiddenInput):
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} form-control".strip()

# Lockout: 5 failed sign-ins, then 5 minutes after the last one.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 300


class CustomAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": _("Incorrect username or password. Please try again."),
        "inactive": _("This account is inactive."),
    }

    def clean(self):
        username = self.cleaned_data.get('username')
        if not username:
            return super().clean()

        from datetime import timedelta

        from django.db import IntegrityError
        from django.db.models import F
        from django.utils import timezone

        from .models import LoginThrottle

        # Sign-in ignores case, so R16LOCK and r16lock share one count.
        key = username.strip().casefold()[:150]
        now = timezone.now()
        rows = LoginThrottle.objects.filter(username=key)
        rows.filter(last_failure_at__lt=now - timedelta(seconds=LOGIN_LOCK_SECONDS)).update(failures=0)
        try:
            LoginThrottle.objects.get_or_create(username=key)
        except IntegrityError:  # a parallel attempt created it first
            pass
        # Take a try before checking the password, with one conditional
        # UPDATE, so parallel attempts can't all read the same count.
        if not rows.filter(failures__lt=LOGIN_MAX_ATTEMPTS).update(
            failures=F("failures") + 1, last_failure_at=now,
        ):
            raise forms.ValidationError(
                _("Too many failed login attempts. Please try again in 5 minutes."),
                code='too_many_attempts',
            )
        try:
            cleaned_data = super().clean()
        except forms.ValidationError as e:
            if e.code != 'invalid_login':
                # Not a wrong password: give the try back.
                rows.filter(failures__gt=0).update(failures=F("failures") - 1)
                raise
            password = self.cleaned_data.get("password")
            if password and self._inactive_account_with_password(username, password):
                raise forms.ValidationError(
                    self.error_messages["inactive"],
                    code="inactive",
                )
            raise
        rows.delete()
        # Old rows for names nobody signs in with any more.
        LoginThrottle.objects.filter(last_failure_at__lt=now - timedelta(days=1)).delete()
        return cleaned_data

    def _inactive_account_with_password(self, username, password):
        user = (
            User.objects.filter(username__iexact=username)
            .order_by("id")
            .first()
        )
        if user is None or not user.check_password(password):
            return False
        return not user.is_active or not user.is_active_user


class RoleLimitMixin:
    """Only a superuser can hand out a role with permissions they don't hold."""

    def __init__(self, *args, editor=None, **kwargs):
        self.editor = editor
        super().__init__(*args, **kwargs)
        field = self.fields.get("role")
        if field is not None and editor is not None and not editor.is_superuser:
            allowed = [r.pk for r in field.queryset if not r.permissions_beyond(editor.role)]
            if self.instance.pk and self.instance.role_id:
                allowed.append(self.instance.role_id)
            field.queryset = field.queryset.filter(pk__in=allowed)

    def clean_role(self):
        role = self.cleaned_data.get("role")
        editor = self.editor
        if role is None or editor is None or editor.is_superuser:
            return role
        if self.instance.pk and self.instance.role_id == role.pk:
            return role  # unchanged, so nothing is being handed out
        if role.permissions_beyond(editor.role):
            raise forms.ValidationError(
                _("You can only assign roles that have no more permissions than your own role.")
            )
        return role


class CustomUserCreationForm(RoleLimitMixin, UserCreationForm):
    status = forms.BooleanField(label=_("Is Active"), required=False, initial=True)
    field_order = (
        'username', 'email', 'first_name', 'last_name',
        'phone', 'user_type', 'branch', 'department', 'role',
        'password1', 'password2', 'status', 'requires_password_change'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)
        if "username" in self.fields:
            self.fields["username"].help_text = ""
            self.fields["username"].widget.attrs.setdefault("placeholder", _("e.g., john.doe"))
        for field in self.fields.values():
            if hasattr(field, 'empty_label'):
                field.empty_label = ''
        for field_name in ("branch", "department"):
            if field_name in self.fields:
                self.fields[field_name].required = False
        _placeholders = {
            "first_name": _("First name"),
            "last_name": _("Last name"),
            "email": _("user@example.com"),
            "phone": _("e.g., +01020481863"),
            "password1": _("Choose a strong password"),
            "password2": _("Repeat the password"),
        }
        for fname, ph in _placeholders.items():
            if fname in self.fields:
                self.fields[fname].widget.attrs.setdefault("placeholder", ph)
        if "phone" in self.fields:
            self.fields["phone"].widget.attrs.update({"inputmode": "tel", "data-normalize-digits": "1"})

    def validate_password_for_user(self, user, password_field_name="password1"):
        # Django puts "too short / too common" under the confirm field; show it
        # under the password that needs changing.
        return super().validate_password_for_user(user, password_field_name=password_field_name)

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            return normalize_digits(phone.strip()) or None
        return phone

    def clean_status(self):
        val = self.cleaned_data.get("status")
        return User.Status.ACTIVE if val else User.Status.INACTIVE

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if not username:
            return username
        username = username.strip().lower()
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("A user with that username already exists."))
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
                self.add_error("branch", _("Branch is required for this user type."))
            cleaned["department"] = None
        elif user_type == User.UserType.SUPPORT:
            if not department:
                self.add_error("department", _("Department is required for this user type."))
            cleaned["branch"] = None

        return cleaned

    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name',
            'phone', 'user_type', 'branch',
            'department', 'role', 'status', 'requires_password_change'
        )


class CustomUserChangeForm(RoleLimitMixin, UserChangeForm):
    status = forms.BooleanField(label=_("Is Active"), required=False)
    field_order = (
        'username', 'email', 'first_name', 'last_name',
        'phone', 'user_type', 'branch', 'department', 'role',
        'password1', 'password2', 'status', 'requires_password_change'
    )
    password1 = forms.CharField(
        label=_("New password"),
        required=False,
        widget=forms.PasswordInput(attrs={'minlength': 4}),
    )
    password2 = forms.CharField(
        label=_("Confirm password"),
        required=False,
        widget=forms.PasswordInput(attrs={'minlength': 4}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)
        if "username" in self.fields:
            self.fields["username"].help_text = ""
            self.fields["username"].widget.attrs.setdefault("placeholder", _("e.g., john.doe"))

        if "password1" in self.fields:
            from django.contrib.auth.password_validation import password_validators_help_text_html
            self.fields["password1"].help_text = password_validators_help_text_html()
        _placeholders = {
            "first_name": _("First name"),
            "last_name": _("Last name"),
            "email": _("user@example.com"),
            "phone": _("e.g., +01020481863"),
            "password1": _("Leave blank to keep current"),
            "password2": _("Repeat new password"),
        }
        for fname, ph in _placeholders.items():
            if fname in self.fields:
                self.fields[fname].widget.attrs.setdefault("placeholder", ph)
            
        if "password2" in self.fields:
            self.fields["password2"].help_text = _("Enter the same password as before, for verification.")
        
        if "phone" in self.fields:
            self.fields["phone"].widget.attrs.update({"inputmode": "tel", "data-normalize-digits": "1"})
            
        if self.instance and self.instance.pk:
            # form.initial (copied from the instance: 'active'/'inactive', both truthy)
            # beats field.initial, so set the boolean there or inactive users show as Active.
            self.initial['status'] = (self.instance.status == User.Status.ACTIVE)
        for field in self.fields.values():
            if hasattr(field, 'empty_label'):
                field.empty_label = ''
        for field_name in ("branch", "department"):
            if field_name in self.fields:
                self.fields[field_name].required = False

        if "password" in self.fields:
            self.fields.pop("password")

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            return normalize_digits(phone.strip()) or None
        return phone

    def clean_status(self):
        val = self.cleaned_data.get("status")
        return User.Status.ACTIVE if val else User.Status.INACTIVE

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if not username:
            return username
        username = username.strip().lower()
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("A user with that username already exists."))
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
                self.add_error("branch", _("Branch is required for this user type."))
            cleaned["department"] = None
        elif user_type == User.UserType.SUPPORT:
            if not department:
                self.add_error("department", _("Department is required for this user type."))
            cleaned["branch"] = None

        return cleaned

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError(_("Passwords do not match."))
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
            'phone', 'user_type', 'branch',
            'department', 'role', 'password1', 'password2', 'status', 'requires_password_change'
        )
