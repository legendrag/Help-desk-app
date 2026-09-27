import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.utils.translation import gettext_lazy as _


def ticket_attachment_path(instance, filename):
    name = get_valid_filename(os.path.basename(filename or "attachment"))
    return f"tickets/{instance.ticket_id}/{name}"


def validate_ticket_attachment(attachment):
    """Enforce ALLOWED_ATTACHMENT_EXTENSIONS and MAX_ATTACHMENT_SIZE."""
    if not attachment:
        return
    name = getattr(attachment, "name", "") or ""
    _, ext = os.path.splitext(name.lower())
    allowed = [e.lower() for e in getattr(settings, "ALLOWED_ATTACHMENT_EXTENSIONS", [])]
    if allowed and ext not in allowed:
        raise ValidationError(
            f"Attachment type '{ext or '(none)'}' is not allowed. "
            f"Allowed: {', '.join(allowed)}"
        )
    max_size = getattr(settings, "MAX_ATTACHMENT_SIZE", None)
    size = getattr(attachment, "size", None)
    if max_size and size is not None and size > max_size:
        raise ValidationError(
            f"Attachment is too large ({size} bytes). Maximum is {max_size} bytes."
        )


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        IN_PROGRESS = "in_progress", _("In Progress")
        WAITING_FOR_BRANCH = "waiting_for_branch", _("Waiting")
        CLOSED = "closed", _("Closed")
        MERGED = "merged", _("Merged")

    class Priority(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")
        URGENT = "urgent", _("Urgent")

    ticket_number = models.CharField(max_length=30, unique=True, db_index=True)
    title = models.CharField(_("Title"), max_length=255)
    description = models.TextField(_("Description"))
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT, related_name="tickets", verbose_name=_("Branch"))
    department = models.ForeignKey("core.Department", on_delete=models.PROTECT, related_name="tickets", verbose_name=_("Department"))
    category = models.ForeignKey("core.Category", on_delete=models.PROTECT, related_name="tickets", verbose_name=_("Category"))
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(_("Priority"), max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    client_name = models.CharField(_("Name"), max_length=255, default="")
    client_phone = models.CharField(_("Phone Number"), max_length=50, default="")
    # Digits-only copy of client_phone using the same strip rules as ticket search.
    client_phone_digits = models.CharField(max_length=50, blank=True, default="", db_index=True)
    # True once a second message exists. Replaces messages.count() for reply audience.
    has_followup_message = models.BooleanField(default=False)
    # True once the unpicked-ticket auto reply has been posted.
    unpicked_notice_sent = models.BooleanField(default=False)
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

        self.client_phone_digits = phone_digits(self.client_phone)

        if not self.ticket_number:
            self.ticket_number = _allocate_ticket_number(self.branch, now)

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
        STATUS_CHANGE = "status_change", _("Status Change")
        TRANSFER_REQUESTED = "transfer_requested", _("Transfer Requested")
        TRANSFER_ACCEPTED = "transfer_accepted", _("Transfer Accepted")
        TRANSFER_DENIED = "transfer_denied", _("Transfer Denied")
        TRANSFER_CANCELLED = "transfer_cancelled", _("Transfer Cancelled")
        MERGED = "merged", _("Ticket Merged")
        PRIORITY_CHANGED = "priority_changed", _("Priority Changed")
        ASSIGNED = "assigned", _("Assigned")
        REOPENED = "reopened", _("Reopened")

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
    # Arabic parallel for system messages. Regular chat messages leave this empty.
    message_ar = models.TextField(blank=True, default="")
    is_system_message = models.BooleanField(default=False)
    attachment = models.FileField(upload_to=ticket_attachment_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
            models.Index(fields=["ticket", "is_system_message"]),
        ]

    def clean(self):
        if not self.is_system_message and self.ticket.status in [Ticket.Status.CLOSED, Ticket.Status.MERGED]:
            raise ValidationError(f"Cannot send message on a {self.ticket.status} ticket.")
        if not self.message and not self.attachment:
            raise ValidationError("Message or attachment is required.")
        if self.attachment:
            validate_ticket_attachment(self.attachment)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TicketDailyCounter(models.Model):
    """One locked row per branch per day for ticket number allocation."""

    branch = models.ForeignKey("core.Branch", on_delete=models.CASCADE, related_name="ticket_daily_counters")
    day = models.DateField()
    last_seq = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["branch", "day"], name="uniq_branch_day_ticket_seq"),
        ]


def phone_digits(value):
    """Strip the same separators ticket search used to remove in SQL."""
    stripped = value or ""
    for char in ("-", " ", "(", ")", ".", "+"):
        stripped = stripped.replace(char, "")
    return stripped


def _max_ticket_seq(prefix):
    max_seq = 0
    numbers = Ticket.objects.filter(ticket_number__startswith=prefix).values_list(
        "ticket_number", flat=True
    )
    for number in numbers:
        try:
            seq_val = int(number.rsplit("-", 1)[-1])
        except (ValueError, AttributeError, TypeError):
            continue
        if seq_val > max_seq:
            max_seq = seq_val
    return max_seq


def _allocate_ticket_number(branch, now):
    """Return the next {BRANCH}-{YYYYMMDD}-{seq:04d} in O(1) after the first of the day."""
    date_part = now.strftime("%Y%m%d")
    branch_code = ((getattr(branch, "code", None) or "BR")).strip().upper()
    prefix = f"{branch_code}-{date_part}-"
    day = now.date()
    with transaction.atomic():
        counter = (
            TicketDailyCounter.objects.select_for_update()
            .filter(branch_id=branch.pk, day=day)
            .first()
        )
        if counter is None:
            seeded = _max_ticket_seq(prefix)
            try:
                counter = TicketDailyCounter.objects.create(
                    branch_id=branch.pk,
                    day=day,
                    last_seq=seeded,
                )
            except IntegrityError:
                counter = TicketDailyCounter.objects.select_for_update().get(
                    branch_id=branch.pk,
                    day=day,
                )
        TicketDailyCounter.objects.filter(pk=counter.pk).update(last_seq=F("last_seq") + 1)
        counter.refresh_from_db(fields=["last_seq"])
        return f"{prefix}{counter.last_seq:04d}"


class TicketMergeHistory(models.Model):
    primary_ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="merge_histories_as_primary")
    secondary_ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="merge_histories_as_secondary")
    merged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    merged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-merged_at"]
        verbose_name_plural = "Ticket merge histories"

