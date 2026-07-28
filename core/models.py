from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Branch(models.Model):
    name = models.CharField(_("Name"), max_length=150)
    code = models.CharField(_("Code"), max_length=50, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Department(models.Model):
    name = models.CharField(_("Name"), max_length=150, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")
        URGENT = "urgent", _("Urgent")

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="categories", verbose_name=_("Department")
    )
    name = models.CharField(_("Name"), max_length=150)
    default_priority = models.CharField(
        _("Default Priority"), max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )

    class Meta:
        ordering = ["department__name", "name"]
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        constraints = [
            models.UniqueConstraint(fields=["department", "name"], name="uniq_category_department_name"),
        ]

    def __str__(self) -> str:
        return f"{self.department.name} - {self.name}"


class Role(TimeStampedModel):
    name = models.CharField(_("Name"), max_length=100, unique=True)
    description = models.TextField(_("Description"), blank=True)

    # Granular Permissions
    can_create_ticket = models.BooleanField(default=True, verbose_name=_("Create Ticket"))
    can_update_ticket = models.BooleanField(default=False, verbose_name=_("Edit Ticket"))
    can_pick_ticket = models.BooleanField(default=False, verbose_name=_("Pick Ticket"))
    can_update_status = models.BooleanField(default=False, verbose_name=_("Update Ticket Status"))
    can_update_closed_ticket = models.BooleanField(default=False, verbose_name=_("Update Status after closed"))
    can_send_message = models.BooleanField(default=True, verbose_name=_("Send Message"))
    can_edit_message = models.BooleanField(default=False, verbose_name=_("Edit Message"))
    can_delete_message = models.BooleanField(default=False, verbose_name=_("Delete Message"))
    can_access_dashboard = models.BooleanField(default=False, verbose_name=_("Access Dashboard"))
    can_view_leaderboard = models.BooleanField(default=False, verbose_name=_("View Agent Leaderboard"))
    can_access_settings = models.BooleanField(default=False, verbose_name=_("Access Settings"))

    # Granular Settings Permissions (Users)
    can_create_user = models.BooleanField(default=False, verbose_name=_("Create User"))
    can_update_user = models.BooleanField(default=False, verbose_name=_("Edit User"))
    can_delete_user = models.BooleanField(default=False, verbose_name=_("Delete User"))

    # Granular Settings Permissions (Branches)
    can_create_branch = models.BooleanField(default=False, verbose_name=_("Create Branch"))
    can_update_branch = models.BooleanField(default=False, verbose_name=_("Edit Branch"))
    can_delete_branch = models.BooleanField(default=False, verbose_name=_("Delete Branch"))

    # Granular Settings Permissions (Departments)
    can_create_department = models.BooleanField(default=False, verbose_name=_("Create Department"))
    can_update_department = models.BooleanField(default=False, verbose_name=_("Edit Department"))
    can_delete_department = models.BooleanField(default=False, verbose_name=_("Delete Department"))

    # Granular Settings Permissions (Categories)
    can_create_category = models.BooleanField(default=False, verbose_name=_("Create Category"))
    can_update_category = models.BooleanField(default=False, verbose_name=_("Edit Category"))
    can_delete_category = models.BooleanField(default=False, verbose_name=_("Delete Category"))

    # Granular Settings Permissions (Roles)
    can_create_role = models.BooleanField(default=False, verbose_name=_("Create Role"))
    can_update_role = models.BooleanField(default=False, verbose_name=_("Edit Role"))
    can_delete_role = models.BooleanField(default=False, verbose_name=_("Delete Role"))

    # Granular Settings Permissions (Email)
    can_manage_email = models.BooleanField(default=False, verbose_name=_("Manage Email Settings"))

    # News Permissions
    can_manage_news = models.BooleanField(default=False, verbose_name=_("Manage News"))

    # Knowledge Base Permissions
    can_access_kb = models.BooleanField(default=False, verbose_name=_("Access Knowledge Base"))
    can_manage_kb = models.BooleanField(default=False, verbose_name=_("Manage Knowledge Base"))

    # System Maintenance Permissions
    can_manage_maintenance = models.BooleanField(default=False, verbose_name=_("Manage System Maintenance"))

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_roles",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.name and self.name.strip().lower() == "admin":
            for field in self._meta.fields:
                if isinstance(field, models.BooleanField):
                    setattr(self, field.name, True)
        super().save(*args, **kwargs)


class EmailSetting(TimeStampedModel):
    ENCRYPTION_CHOICES = (
        ("none", _("None")),
        ("tls", _("TLS")),
        ("ssl", _("SSL")),
    )

    smtp_host = models.CharField(_("SMTP Host"), max_length=255)
    smtp_port = models.PositiveIntegerField(_("SMTP Port"), default=587)
    smtp_email = models.EmailField(_("SMTP Email"))
    smtp_password = models.CharField(_("SMTP Password"), max_length=255)
    encryption = models.CharField(_("Encryption"), max_length=10, choices=ENCRYPTION_CHOICES, default="tls")
    from_name = models.CharField(_("From Name"), max_length=255)
    from_email = models.EmailField(_("From Email"))
    is_active = models.BooleanField(_("Active"), default=True)
    notify_new_ticket = models.BooleanField(default=True, verbose_name=_("New tickets"))
    notify_ticket_picked = models.BooleanField(default=True, verbose_name=_("Ticket picked"))
    notify_ticket_message = models.BooleanField(default=True, verbose_name=_("Ticket messages"))
    notify_ticket_status = models.BooleanField(default=True, verbose_name=_("Status changes"))
    notify_ticket_update = models.BooleanField(default=True, verbose_name=_("Ticket updates"))
    notify_announcement = models.BooleanField(default=True, verbose_name=_("Announcements"))

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = _("Email Setting")
        verbose_name_plural = _("Email Settings")
        constraints = [
            models.UniqueConstraint(fields=["is_active"], condition=Q(is_active=True), name="uniq_active_email_setting"),
        ]

    def __str__(self) -> str:
        return f"SMTP {self.smtp_host}:{self.smtp_port}"


class EmailTemplate(TimeStampedModel):
    """Per-event subject/body for notification emails (plain text + merge tokens)."""

    class EventType(models.TextChoices):
        NEW_TICKET = "new_ticket", _("New ticket")
        TICKET_PICKED = "ticket_picked", _("Ticket picked")
        TICKET_MESSAGE = "ticket_message", _("Ticket reply")
        TICKET_STATUS = "ticket_status", _("Status change")
        TICKET_UPDATE = "ticket_update", _("Ticket update")
        TRANSFER_REQUESTED = "transfer_requested", _("Transfer requested")
        TRANSFER_ACCEPTED = "transfer_accepted", _("Transfer accepted")
        TRANSFER_DENIED = "transfer_denied", _("Transfer declined")
        ANNOUNCEMENT = "announcement", _("Announcement")

    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
        unique=True,
    )
    subject = models.CharField(_("Subject"), max_length=255)
    body = models.TextField(_("Body"))

    class Meta:
        ordering = ["event_type"]
        verbose_name = _("Email template")
        verbose_name_plural = _("Email templates")

    def __str__(self) -> str:
        return self.get_event_type_display()
