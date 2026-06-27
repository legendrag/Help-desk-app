from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


def ticket_attachment_path(instance, filename):
    return f"tickets/{instance.ticket_id}/{filename}"


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        WAITING_FOR_BRANCH = "waiting_for_branch", "Waiting for Branch"
        CLOSED = "closed", "Closed"
        MERGED = "merged", "Merged"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    ticket_number = models.CharField(max_length=30, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT, related_name="tickets")
    department = models.ForeignKey("core.Department", on_delete=models.PROTECT, related_name="tickets")
    category = models.ForeignKey("core.Category", on_delete=models.PROTECT, related_name="tickets")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    client_name = models.CharField(max_length=255, default="")
    client_phone = models.CharField(max_length=50, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_tickets",
    )
    pending_transfer_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_transfers_to",
    )
    pending_transfer_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_transfers_by",
    )
    version = models.PositiveIntegerField(default=1)
    
    # Time Tracking
    picked_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_status_change_at = models.DateTimeField(default=timezone.now)
    total_pending_duration_seconds = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["department", "status"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self):
        return self.ticket_number

    def clean(self):
        if self.category_id and self.department_id and self.category.department_id != self.department_id:
            raise ValidationError({"category": "Category must belong to selected department."})

        if self.status == self.Status.MERGED and not self.merged_into_id:
            raise ValidationError({"merged_into": "Merged ticket must have a target ticket."})

        # Use cached previous state from save() to avoid a redundant query.
        previous = getattr(self, "_previous", None)
        if previous is None and self.pk:
            previous = Ticket.objects.filter(pk=self.pk).only("status").first()
        if previous and previous.status == self.Status.MERGED and self.status != self.Status.MERGED:
            raise ValidationError("Cannot un-merge a merged ticket.")

    def save(self, *args, **kwargs):
        now = timezone.now()
        previous_status = None
        previous_last_change = None

        # Fetch previous state once and cache it for clean() to reuse.
        self._previous = None
        if self.pk:
            self._previous = Ticket.objects.filter(pk=self.pk).only(
                "status", "last_status_change_at"
            ).first()
            if self._previous:
                previous_status = self._previous.status
                previous_last_change = self._previous.last_status_change_at

        if not self.ticket_number:
            date_part = now.strftime("%Y%m%d")
            branch_code = (self.branch.code or "BR").strip().upper()
            prefix = f"{branch_code}-{date_part}-"

            with transaction.atomic():
                existing = (
                    Ticket.objects.select_for_update()
                    .filter(ticket_number__startswith=prefix)
                    .values_list("ticket_number", flat=True)
                )
                max_seq = 0
                for number in existing:
                    try:
                        seq_str = number.rsplit("-", 1)[-1]
                        seq_val = int(seq_str)
                        if seq_val > max_seq:
                            max_seq = seq_val
                    except (ValueError, AttributeError):
                        continue

                self.ticket_number = f"{prefix}{max_seq + 1:04d}"

        if previous_status and previous_status != self.status:
            if previous_status == Ticket.Status.WAITING_FOR_BRANCH:
                start_time = previous_last_change or self.created_at or now
                delta = (now - start_time).total_seconds()
                if delta > 0:
                    self.total_pending_duration_seconds += int(delta)

            if self.status == Ticket.Status.IN_PROGRESS and not self.picked_at:
                self.picked_at = now

            if self.status == Ticket.Status.CLOSED and not self.closed_at:
                self.closed_at = now

            self.last_status_change_at = now

        elif not self.last_status_change_at:
            self.last_status_change_at = now

        self.full_clean()
        super().save(*args, **kwargs)


class TicketStatusHistory(models.Model):
    class EventType(models.TextChoices):
        STATUS_CHANGE = "status_change", "Status Change"
        TRANSFER_REQUESTED = "transfer_requested", "Transfer Requested"
        TRANSFER_ACCEPTED = "transfer_accepted", "Transfer Accepted"
        TRANSFER_DENIED = "transfer_denied", "Transfer Denied"
        TRANSFER_CANCELLED = "transfer_cancelled", "Transfer Cancelled"
        MERGED = "merged", "Ticket Merged"
        PRIORITY_CHANGED = "priority_changed", "Priority Changed"
        ASSIGNED = "assigned", "Assigned"
        REOPENED = "reopened", "Reopened"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=30, choices=Ticket.Status.choices, blank=True, default="")
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        default=EventType.STATUS_CHANGE,
    )
    detail = models.CharField(max_length=255, blank=True, default="")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "Ticket status histories"
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
        ]


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ticket_messages")
    reply_to = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies")
    message = models.TextField(blank=True)
    is_system_message = models.BooleanField(default=False)
    attachment = models.FileField(upload_to=ticket_attachment_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
        ]

    def clean(self):
        if self.ticket.status in [Ticket.Status.CLOSED, Ticket.Status.MERGED]:
            raise ValidationError(f"Cannot send message on a {self.ticket.status} ticket.")
        if not self.message and not self.attachment:
            raise ValidationError("Message or attachment is required.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TicketMergeHistory(models.Model):
    primary_ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="merge_histories_as_primary")
    secondary_ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="merge_histories_as_secondary")
    merged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    merged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-merged_at"]
        verbose_name_plural = "Ticket merge histories"

