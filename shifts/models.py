from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class ShiftType(TimeStampedModel):
    class NightMode(models.TextChoices):
        AUTO = "auto", _("Automatic")
        ALWAYS = "always", _("Always")
        NEVER = "never", _("Never")

    department = models.ForeignKey(
        "core.Department",
        on_delete=models.PROTECT,
        related_name="shift_types",
        verbose_name=_("Department"),
    )
    name = models.CharField(_("Name"), max_length=100)
    start_time = models.TimeField(_("Start time"))
    end_time = models.TimeField(_("End time"))
    is_night = models.BooleanField(default=False, editable=False, verbose_name=_("Night"))
    night_mode = models.CharField(
        _("Counts as night shift"),
        max_length=10,
        choices=NightMode.choices,
        default=NightMode.AUTO,
    )
    colour = models.CharField(
        _("Colour"),
        max_length=7,
        default="#6366f1",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")],
    )
    archived = models.BooleanField(_("Archived"), default=False)

    class Meta:
        ordering = ["department__name", "name"]
        verbose_name = _("Shift type")
        verbose_name_plural = _("Shift types")
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name"],
                name="uniq_shift_type_department_name",
            ),
        ]
        indexes = [
            models.Index(fields=["department", "archived"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.start_time and self.end_time and self.department_id:
            from shifts.services import is_night_shift, night_window_for

            self.is_night = is_night_shift(
                self.start_time,
                self.end_time,
                *night_window_for(self.department),
                mode=self.night_mode,
            )
        super().save(*args, **kwargs)


class ShiftAssignment(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shift_assignments",
        verbose_name=_("User"),
    )
    shift_type = models.ForeignKey(
        ShiftType,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name=_("Shift type"),
    )
    date = models.DateField(_("Date"))
    start_time_override = models.TimeField(_("Start override"), null=True, blank=True)
    end_time_override = models.TimeField(_("End override"), null=True, blank=True)
    times_set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shift_times_set",
        verbose_name=_("Times set by"),
    )
    times_set_at = models.DateTimeField(_("Times set at"), null=True, blank=True)
    checked_in_at = models.DateTimeField(_("Checked in at"), null=True, blank=True)
    checked_out_at = models.DateTimeField(_("Checked out at"), null=True, blank=True)
    # When the agent pressed check in. Unlike checked_in_at it survives the
    # shift ending, so the work hours report can start the shift from it.
    arrived_at = models.DateTimeField(_("Arrived at"), null=True, blank=True)

    class Meta:
        ordering = ["date", "user_id"]
        verbose_name = _("Shift assignment")
        verbose_name_plural = _("Shift assignments")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date", "shift_type"],
                name="uniq_shift_assignment_user_date_type",
            ),
        ]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["shift_type", "date"]),
        ]

    def clean(self):
        start = self.start_time_override
        end = self.end_time_override
        if (start is None) ^ (end is None):
            raise ValidationError(_("Enter both start and end, or leave both blank."))
        if start is not None and start == end:
            raise ValidationError(_("Start and end must differ."))
        if start is None and (self.times_set_by_id or self.times_set_at):
            raise ValidationError(_("Clear the audit fields when the override is cleared."))
        if start is not None and not (self.times_set_by_id and self.times_set_at):
            raise ValidationError(_("Record who set the times."))


class DepartmentShiftSettings(TimeStampedModel):
    department = models.OneToOneField(
        "core.Department",
        on_delete=models.CASCADE,
        related_name="shift_settings",
        verbose_name=_("Department"),
    )
    night_starts_at = models.TimeField(_("Night starts at"), default=time(18, 0))
    night_ends_at = models.TimeField(_("Night ends at"), default=time(6, 0))

    class Meta:
        verbose_name = _("Shift settings")
        verbose_name_plural = _("Shift settings")

    def __str__(self):
        from shifts.clock import format_clock

        return f"{self.department} · {format_clock(self.night_starts_at)}–{format_clock(self.night_ends_at)}"
