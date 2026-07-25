from django.conf import settings
from django.db import models
from django.db.models import Q


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Branch(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=150)
    default_priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)

    class Meta:
        ordering = ["department__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["department", "name"], name="uniq_category_department_name"),
        ]

    def __str__(self) -> str:
        return f"{self.department.name} - {self.name}"


class Role(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Granular Permissions
    can_create_ticket = models.BooleanField(default=True, verbose_name="Create Ticket")
    can_update_ticket = models.BooleanField(default=False, verbose_name="Edit Ticket")
    can_pick_ticket = models.BooleanField(default=False, verbose_name="Pick Ticket")
    can_update_status = models.BooleanField(default=False, verbose_name="Update Ticket Status")
    can_update_closed_ticket = models.BooleanField(default=False, verbose_name="Update Status after closed")
    can_send_message = models.BooleanField(default=True, verbose_name="Send Message")
    can_edit_message = models.BooleanField(default=False, verbose_name="Edit Message")
    can_delete_message = models.BooleanField(default=False, verbose_name="Delete Message")
    can_access_dashboard = models.BooleanField(default=False, verbose_name="Access Dashboard")
    can_view_leaderboard = models.BooleanField(default=False, verbose_name="View Agent Leaderboard")
    can_access_settings = models.BooleanField(default=False, verbose_name="Access Settings")
    
    # Granular Settings Permissions (Users)
    can_create_user = models.BooleanField(default=False, verbose_name="Create User")
    can_update_user = models.BooleanField(default=False, verbose_name="Edit User")
    can_delete_user = models.BooleanField(default=False, verbose_name="Delete User")

    # Granular Settings Permissions (Branches)
    can_create_branch = models.BooleanField(default=False, verbose_name="Create Branch")
    can_update_branch = models.BooleanField(default=False, verbose_name="Edit Branch")
    can_delete_branch = models.BooleanField(default=False, verbose_name="Delete Branch")

    # Granular Settings Permissions (Departments)
    can_create_department = models.BooleanField(default=False, verbose_name="Create Department")
    can_update_department = models.BooleanField(default=False, verbose_name="Edit Department")
    can_delete_department = models.BooleanField(default=False, verbose_name="Delete Department")

    # Granular Settings Permissions (Categories)
    can_create_category = models.BooleanField(default=False, verbose_name="Create Category")
    can_update_category = models.BooleanField(default=False, verbose_name="Edit Category")
    can_delete_category = models.BooleanField(default=False, verbose_name="Delete Category")

    # Granular Settings Permissions (Roles)
    can_create_role = models.BooleanField(default=False, verbose_name="Create Role")
    can_update_role = models.BooleanField(default=False, verbose_name="Edit Role")
    can_delete_role = models.BooleanField(default=False, verbose_name="Delete Role")

    # Granular Settings Permissions (Email)
    can_manage_email = models.BooleanField(default=False, verbose_name="Manage Email Settings")
    
    # News Permissions
    can_manage_news = models.BooleanField(default=False, verbose_name="Manage News")
    
    # Knowledge Base Permissions
    can_access_kb = models.BooleanField(default=False, verbose_name="Access Knowledge Base")
    can_manage_kb = models.BooleanField(default=False, verbose_name="Manage Knowledge Base")
    
    # System Maintenance Permissions
    can_manage_maintenance = models.BooleanField(default=False, verbose_name="Manage System Maintenance")
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_roles",
    )

    class Meta:
        ordering = ["name"]

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
        ("none", "None"),
        ("tls", "TLS"),
        ("ssl", "SSL"),
    )

    smtp_host = models.CharField(max_length=255)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_email = models.EmailField()
    smtp_password = models.CharField(max_length=255)
    encryption = models.CharField(max_length=10, choices=ENCRYPTION_CHOICES, default="tls")
    from_name = models.CharField(max_length=255)
    from_email = models.EmailField()
    is_active = models.BooleanField(default=True)
    notify_new_ticket = models.BooleanField(default=True, verbose_name="New tickets")
    notify_ticket_picked = models.BooleanField(default=True, verbose_name="Ticket picked")
    notify_ticket_message = models.BooleanField(default=True, verbose_name="Ticket messages")
    notify_ticket_status = models.BooleanField(default=True, verbose_name="Status changes")
    notify_ticket_update = models.BooleanField(default=True, verbose_name="Ticket updates")
    notify_announcement = models.BooleanField(default=True, verbose_name="Announcements")

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["is_active"], condition=Q(is_active=True), name="uniq_active_email_setting"),
        ]

    def __str__(self) -> str:
        return f"SMTP {self.smtp_host}:{self.smtp_port}"


class EmailBrand(TimeStampedModel):
    """Singleton branding for notification emails."""

    class TableStyle(models.TextChoices):
        PLAIN = "plain", "Plain"
        STRIPED = "striped", "Striped rows"
        FILLED = "filled", "Filled labels"

    brand_name = models.CharField(max_length=100, default="mlamehticket")
    accent_color = models.CharField(max_length=7, default="#4f46e5")
    page_background = models.CharField(max_length=7, default="#f8fafc")
    card_background = models.CharField(max_length=7, default="#ffffff")
    table_header_bg = models.CharField(max_length=7, default="#f8fafc")
    table_border_color = models.CharField(max_length=7, default="#e2e8f0")
    text_color = models.CharField(max_length=7, default="#0f172a")
    muted_text_color = models.CharField(max_length=7, default="#64748b")
    table_style = models.CharField(
        max_length=20,
        choices=TableStyle.choices,
        default=TableStyle.STRIPED,
    )
    footer_note = models.TextField(
        default=(
            "You’re receiving this because email notifications are enabled "
            "for your mlamehticket account."
        )
    )

    class Meta:
        verbose_name = "Email Brand"
        verbose_name_plural = "Email Brand"

    def __str__(self) -> str:
        return f"Email brand ({self.brand_name})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        from notifications.email_messages import ensure_email_designer_defaults

        ensure_email_designer_defaults()
        return cls.objects.get(pk=1)


class EmailMessage(TimeStampedModel):
    class EventType(models.TextChoices):
        NEW_TICKET = "new_ticket", "New ticket"
        TICKET_PICKED = "ticket_picked", "Ticket picked"
        TICKET_MESSAGE = "ticket_message", "Reply"
        TICKET_STATUS = "ticket_status", "Status change"
        TICKET_UPDATE = "ticket_update", "Ticket update"
        TRANSFER_REQUESTED = "transfer_requested", "Transfer requested"
        TRANSFER_ACCEPTED = "transfer_accepted", "Transfer accepted"
        TRANSFER_DENIED = "transfer_denied", "Transfer declined"
        ANNOUNCEMENT = "announcement", "Announcement"

    event_type = models.CharField(max_length=40, choices=EventType.choices, unique=True)
    subject = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    opening = models.TextField(blank=True)
    message_label = models.CharField(max_length=100, blank=True)
    button_label = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["event_type"]
        verbose_name = "Email Message"
        verbose_name_plural = "Email Messages"

    def __str__(self) -> str:
        return self.get_event_type_display()
