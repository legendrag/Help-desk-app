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
    title = models.CharField(max_length=255)
    message = models.TextField()
    # Optional structured fields (reserved; in-app text uses title/message).
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

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
