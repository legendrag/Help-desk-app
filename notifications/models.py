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
        SHIFT = "shift", "Shift"
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
            models.Index(fields=["recipient", "title", "link", "created_at"]),
        ]

    def arabic_title(self):
        return self.title_ar or (self.params or {}).get("title_ar") or ""

    def arabic_message(self):
        return self.message_ar or (self.params or {}).get("message_ar") or ""

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"


class EmailOutbox(models.Model):
    """A queued email job, saved so a crash or forced restart can't lose it.

    ``func`` is the dotted path of a module-level job (e.g.
    ``notifications.email_jobs.send_new_ticket_email``) and ``args``/``kwargs``
    are its JSON arguments (ids and strings). Sent rows are deleted; rows that
    failed every attempt stay as ``failed`` for an admin to look at, and are
    removed after EMAIL_OUTBOX_FAILED_KEEP_DAYS. ``sent_keys`` records which
    recipients already got it, so a crash mid-send doesn't mail them again.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        FAILED = "failed", "Failed"

    func = models.CharField(max_length=200)
    args = models.JSONField(default=list, blank=True)
    kwargs = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    retry_delay = models.PositiveIntegerField(default=5, help_text="Seconds; multiplied by the attempt number.")
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True, default="")
    sent_keys = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"])]
        verbose_name = "Queued email"
        verbose_name_plural = "Queued emails"

    def __str__(self):
        return f"{self.func} ({self.status}, attempt {self.attempts}/{self.max_attempts})"
