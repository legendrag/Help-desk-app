from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("Username is required")
        email = self.normalize_email(email) if email else None
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", User.UserType.SUPPORT)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    class UserType(models.TextChoices):
        BRANCH = "branch", "Needs Support"
        SUPPORT = "support", "Support Agent"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    role = models.ForeignKey("core.Role", on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    branch = models.ForeignKey(
        "core.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    department = models.ForeignKey(
        "core.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.BRANCH)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    requires_password_change = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    class Meta:
        indexes = [
            models.Index(fields=["user_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["department"]),
            models.Index(fields=["branch"]),
        ]

    def __str__(self) -> str:
        return self.username

    @property
    def is_active_user(self):
        return self.status == self.Status.ACTIVE

    def save(self, *args, **kwargs):
        # Normalize username/email for case-insensitive handling.
        if self.username:
            self.username = self.username.strip().lower()
        if not self.email:
            self.email = None
        super().save(*args, **kwargs)


