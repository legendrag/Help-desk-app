from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class ShiftType(TimeStampedModel):
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
        self.is_night = self.end_time < self.start_time
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

    class Meta:
        ordering = ["date", "user_id"]
        verbose_name = _("Shift assignment")
        verbose_name_plural = _("Shift assignments")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                name="uniq_shift_assignment_user_date",
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
