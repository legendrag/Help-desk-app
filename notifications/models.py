from accounts.models import User
from django.db import models
from django.utils import timezone


class InAppNotification(models.Model):
    class NotificationType(models.TextChoices):
        NEW_TICKET = "new_ticket", "New Ticket"
        TICKET_PICKED = "ticket_picked", "Ticket Picked"
        STATUS_CHANGE = "status_change", "Status Change"
        MESSAGE = "message", "Message"
        TRANSFER = "transfer", "Transfer"
        ANNOUNCEMENT = "announcement", "Announcement"
        GENERAL = "general", "General"

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    # English is always the source of truth for dedupe, web push, and fallback.
    title = models.CharField(max_length=255)
    message = models.TextField()
    # Arabic parallel — must remain on the model whenever the DB columns exist
    # (migration 0007). Omitting them from INSERT leaves NULL in NOT NULL
    # columns and silently kills every notification create.
    title_ar = models.CharField(max_length=255, blank=True, default="")
    message_ar = models.TextField(blank=True, default="")
    title_key = models.CharField(max_length=255, blank=True, default="")
    message_key = models.TextField(blank=True, default="")
    params = models.JSONField(default=dict, blank=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def arabic_title(self):
        return self.title_ar or (self.params or {}).get("title_ar") or ""

    def arabic_message(self):
        return self.message_ar or (self.params or {}).get("message_ar") or ""

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
