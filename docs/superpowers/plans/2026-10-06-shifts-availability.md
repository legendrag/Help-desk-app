# Shifts & availability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-contained `shifts` app for a Saturday–Friday department rota, night-shift hour entry, day-shift check-in, and an Available now board.

**Architecture:** One new Django app follows `kb` and `news`: a single `views.py`, a single `tests.py`, global URL names (no `app_name`), templates in `templates/shifts/`, and new CSS/JS files in the existing `static/` tree. Interval math lives in `shifts/services.py`. Authorization lives in `shifts/access.py`. The only shared edits are the Role flag, the Settings role checkbox, the sidebar link, three spots in `static/js/app-shell.js`, `INSTALLED_APPS`, `config/urls.py`, Arabic catalogs, and two doc rows.

**Tech Stack:** Django 6, `config.settings`, `python manage.py test` (not pytest), HTMX, `core.http_cache`, MySQL in production / SQLite in the default test run, `USE_TZ = True`.

## Global Constraints

Every task includes these. Copy the values. Do not invent new ones.

- Week start is Saturday. `saturday = day - timedelta(days=(day.weekday() - 5) % 7)` with Monday `weekday() == 0` and Saturday `weekday() == 5`. A Wednesday snaps to the previous Saturday. A Saturday stays. The week is that Saturday through the next Friday (7 dates). Column order in the DOM is Saturday first. Do not reverse columns for Arabic. `html[dir=rtl]` mirrors the table, so Saturday appears on the right.
- `view=month` normalizes to the first of that month. It does not snap to Saturday.
- One `ShiftAssignment` per `(user, date)`.
- Intervals are half-open `[start, end)`. Touching at the end instant does not overlap. A shift that ends at 06:00 does not cover the 06:00 hour and is not “on shift” at 06:00.
- An overnight shift is stored on the start date. End time earlier than start time means the end is on `date + 1 day`.
- `ShiftType.is_night` is true exactly when `end_time < start_time`. It is not an editable checkbox.
- Night hours: if `shift_type.is_night`, every clipped effective minute is night hours (including 18:00–23:00). Otherwise every clipped minute is day hours, even if the interval crosses midnight.
- The length tool’s “hours after midnight” is informational and is not the night-hours total.
- `WORKER_HOURS_LOOKBACK_DAYS = 7`. Worker may save or reset when `date >= local today - 7 days`. Eight days ago is rejected. Seven days ago is accepted.
- Worker length is greater than 0 and at most 16 hours (960 minutes). 16 hours exactly is allowed. The cell modal has no 16-hour cap.
- `CHECK_IN_EARLY_MINUTES = 30`. Check-in is only for a non-night type, only for the owning `user_type == "support"`, only when `date` is local today, and only when `effective_start - 30 minutes <= now < effective_end`.
- Day-shift Available now requires `checked_in_at` and now inside the effective interval. Early check-in does not show the person before the effective start. Night shifts ignore `checked_in_at`.
- Repeat N is an integer from 1 through 12.
- `NIGHT_ROTATION_LOOKBACK_DAYS = 14`. Rotation counts night-type assignments, one per date. It never overwrites an existing row.
- Copy and repeat do not copy worker-entered overrides and do not copy `checked_in_at`. Friday’s overnight tail is not written as a Saturday assignment. Saturday’s new cell comes only from the previous Saturday.
- Worker-entered means both overrides are set, `times_set_by_id` is set, and `is_shift_manager(times_set_by)` is false. Both overrides set and `times_set_by` null counts as manager-set.
- Poll only Available now: `every 20s [!document.hidden]`, `data-no-progress`. No new websocket, cache, or dependency.
- Date filters use `date__gte`, `date__lte`, and `date__in` on the `DateField`. Never `__date` or `TruncDate` on a datetime.
- Authorization failures are HTTP 403. Worker time and check-in window failures re-render with HTTP 200 and a translated message.
- `TIME_ZONE` is `settings.TIME_ZONE`. `USE_TZ` is true. Build “today” with `timezone.localdate()`.
- Tests: `python manage.py test <label>` uses `config.settings`. `'test' in sys.argv` sets `MIGRATION_MODULES` so migrations do not run. Do not add pytest or freezegun. Freeze time with `unittest.mock.patch` on `django.utils.timezone.now` and `django.utils.timezone.localdate`. Views call `timezone.now()` and `timezone.localdate()` on that module.
- Do not edit `static/css/modern.css`, `dark-mode.css`, `rtl.css`, `style.css`, anything under `tickets/`, `kb/`, `news/`, `notifications/`, `webpush/`, dashboard templates, or `core/session_middleware.py`.
- User-visible sentences are exactly these English strings (Task 14 translates them): `"Start and end must differ."`, `"Shift type name must be at least 2 characters long."`, `"Enter both start and end, or leave both blank."`, `"Only active support users in this department can be assigned."`, `"Archived shift types cannot be assigned."`, `"That time does not exist on this date."`, `"Enter a number of weeks from 1 to 12."`, `"Nothing to copy."`, `"Copied %(count)s shifts."`, `"Repeated %(count)s shifts."`, `"Filled %(count)s night shifts."`, `"This department has no night shift."`, `"Nobody available on %(date)s."`, `"You can only change hours from the last 7 days onward."`, `"Enter both a start and an end time."`, `"This shift must be longer than 0 hours and no more than 16 hours."`, `"You can check in from 30 minutes before this shift starts."`, `"This shift has ended."`, `"You are not assigned to a department."`, `"Nobody on shift now"`, `"You are on shift until %(end)s."`, `"You have no upcoming shifts."`, `"Set by worker"`, `"Not in this department"`, `"Inactive"`, `"Not checked in"`, `"Missed"`, `"Check in"`, `"Clear check-in"`, `"Set my hours"`, `"Reset to shift default"`.

This is one app, so it stays one plan. Tasks are ordered. Do not start Task N+1 before Task N’s tests pass.

## File tree

```text
shifts/__init__.py
shifts/apps.py
shifts/admin.py
shifts/models.py
shifts/services.py
shifts/access.py
shifts/forms.py
shifts/views.py
shifts/urls.py
shifts/tests.py
shifts/migrations/__init__.py
shifts/migrations/0001_initial.py
templates/shifts/shell.html
templates/shifts/rota.html
templates/shifts/rota_grid.html
templates/shifts/cell_form.html
templates/shifts/types.html
templates/shifts/type_form.html
templates/shifts/calculator.html
templates/shifts/calc_hours.html
templates/shifts/calc_rotation.html
templates/shifts/calc_length.html
templates/shifts/calc_coverage.html
templates/shifts/available.html
templates/shifts/available_board.html
templates/shifts/mine.html
templates/shifts/mine_row.html
templates/shifts/check_in_panel.html
templates/shifts/team.html
static/css/shifts.css
static/js/shifts.js
```

Also modify: `core/models.py`, `core/forms.py`, `core/tests.py`, `core/migrations/0023_role_can_manage_shifts.py`, `templates/core/management/form_partial.html`, `templates/base.html`, `static/js/app-shell.js`, `config/settings.py`, `config/urls.py`, `locale/ar/LC_MESSAGES/django.po`, `locale/ar/LC_MESSAGES/django.mo`, `docs/reference/permissions-matrix.md`, `PROJECT_STANDARDS.md`.

Why this shape: `kb`, `news`, `accounts`, and `core` each use one views module and one `tests.py`. `tickets/template_views.py` is already large and was not split. Do not create `shifts/views/` or `shifts/tests/`. HTML for every app lives in `templates/<app>/`, not inside the app. CSS and JS live in `static/css/` and `static/js/`. No urls file sets `app_name`. Reverse `"shifts_home"`, never `"shifts:shifts_home"`.

## Shared test helpers

Task 2 pastes this once at the top of `shifts/tests.py` under the imports. Later tasks only append classes. Do not copy the helpers into a second module.

```python
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Department, Role
from shifts.models import ShiftAssignment, ShiftType

User = get_user_model()


def aware(y, m, d, hh, mm=0):
    return timezone.make_aware(datetime(y, m, d, hh, mm))


def make_department(name="Desk"):
    return Department.objects.create(name=name)


def make_role(name="Agent", **flags):
    return Role.objects.create(name=name, **flags)


def make_user(username, user_type, department=None, role=None, superuser=False, first_name="", last_name=""):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="test-pass-123",
        user_type=user_type,
        department=department,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    if superuser:
        user.is_superuser = True
        user.is_staff = True
        user.save()
    return user


def make_shift_type(department, name="Night", start=time(22, 0), end=time(6, 0), archived=False):
    return ShiftType.objects.create(
        department=department,
        name=name,
        start_time=start,
        end_time=end,
        colour="#336699",
        archived=archived,
    )


def make_assignment(user, shift_type, on, start=None, end=None):
    return ShiftAssignment.objects.create(
        user=user,
        shift_type=shift_type,
        date=on,
        start_time_override=start,
        end_time_override=end,
        times_set_by=user if start and end else None,
        times_set_at=timezone.now() if start and end else None,
    )
```

`make_assignment` sets `times_set_by` to the assignee. Tests that need a manager-set override pass the manager afterwards: `row.times_set_by = manager; row.save()`.

## Task 1: Role flag `can_manage_shifts`

**Files:**
- Modify: `core/models.py` (the `Role` flag block, after `can_manage_maintenance`)
- Create: `core/migrations/0023_role_can_manage_shifts.py`
- Modify: `core/forms.py` (`RoleForm.Meta.widgets` and `fields` only)
- Modify: `templates/core/management/form_partial.html` (Access card only)
- Test: `core/tests.py`

**Interfaces:**
- Consumes: existing `Role.save()` loop that sets every `BooleanField` true when `name.strip().lower() == "admin"`.
- Produces: `Role.can_manage_shifts: bool`, default false. Verbose name `"Manage Shifts"`.

- [ ] **Step 1: Write the failing test**

Append to `core/tests.py`. Add `Role` to the existing `core.models` import.

```python
class ManageShiftsFlagTests(TestCase):
    def test_admin_role_name_forces_the_flag(self):
        role = Role(name=" Admin ", can_manage_shifts=False)
        role.save()
        role.refresh_from_db()
        self.assertTrue(role.can_manage_shifts)

    def test_other_role_keeps_false(self):
        role = Role.objects.create(name="Desk agent", can_manage_shifts=False)
        self.assertFalse(role.can_manage_shifts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.tests.ManageShiftsFlagTests -v 1`

Expected: FAIL. `Role()` does not accept `can_manage_shifts` yet (`TypeError` or `FieldError`).

- [ ] **Step 3: Write the minimal implementation**

In `core/models.py`, immediately after `can_manage_maintenance`:

```python
can_manage_shifts = models.BooleanField(default=False, verbose_name=_("Manage Shifts"))
```

Do not edit `Role.save()`. The existing BooleanField loop already covers this flag.

Create `core/migrations/0023_role_can_manage_shifts.py`:

```python
from django.db import migrations, models


def grant_admin_roles(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    for role in Role.objects.all():
        if role.name and role.name.strip().lower() == "admin":
            role.can_manage_shifts = True
            role.save(update_fields=["can_manage_shifts"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_alter_i18n_verbose_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_manage_shifts",
            field=models.BooleanField(default=False, verbose_name="Manage Shifts"),
        ),
        migrations.RunPython(grant_admin_roles, noop),
    ]
```

In `core/forms.py`, add `'can_manage_shifts': forms.CheckboxInput(),` after `can_manage_maintenance` in `widgets`, and `'can_manage_maintenance',`’s neighbor `'can_manage_shifts',` at the end of `fields`.

In `templates/core/management/form_partial.html`, inside the Access `perm-list`, after the maintenance checkbox:

```html
<label class="perm-item">{{ form.can_manage_shifts }} <span>{{ form.can_manage_shifts.label }}</span></label>
```

Do not add `can_manage_shifts` to the `support` or `branch` arrays inside `applyRolePreset`. `full` uses `setAll(true)` and already includes every checkbox.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test core.tests.ManageShiftsFlagTests -v 1`

Expected: `OK`. The `RunPython` does not run under tests because `MIGRATION_MODULES` is installed. The model `save()` test is the check that counts.

- [ ] **Step 5: Commit**

```bash
git add core/models.py core/forms.py core/tests.py core/migrations/0023_role_can_manage_shifts.py templates/core/management/form_partial.html
git commit -m "Add can_manage_shifts role flag"
```

## Task 2: App scaffold, models, admin, URLs

**Files:**
- Create: `shifts/__init__.py`, `shifts/apps.py`, `shifts/admin.py`, `shifts/models.py`, `shifts/forms.py` (placeholder module; Task 5 replaces it with `ShiftTypeForm`), `shifts/migrations/__init__.py`, `shifts/migrations/0001_initial.py`, `shifts/urls.py` (empty `urlpatterns`), `shifts/tests.py`
- Modify: `config/settings.py` (`INSTALLED_APPS` only). Do not edit `config/urls.py` in this task.

**Interfaces:**
- Consumes: `core.models.TimeStampedModel`, `core.Department`, `accounts.User`.
- Produces:
  - `ShiftType(department, name, start_time, end_time, is_night, colour, archived)`
  - `ShiftAssignment(user, shift_type, date, start_time_override, end_time_override, times_set_by, times_set_at, checked_in_at)`
  - `ShiftType.save()` sets `is_night = end_time < start_time`
  - URL include `path("shifts/", include("shifts.urls"))` added in Task 4 when `shifts/urls.py` exists. This task creates an empty `urlpatterns = []` so the include can wait until Task 4. Do not include the urls module until Task 4.

- [ ] **Step 1: Write the failing test**

Create `shifts/tests.py` with the imports and helpers from “Shared test helpers”, plus:

```python
class ShiftTypeNightFlagTests(TestCase):
    def test_end_before_start_is_night(self):
        department = make_department()
        row = make_shift_type(department, start=time(22, 0), end=time(6, 0))
        self.assertTrue(row.is_night)

    def test_same_day_span_is_not_night(self):
        department = make_department()
        row = make_shift_type(department, name="Day", start=time(9, 0), end=time(17, 0))
        self.assertFalse(row.is_night)

    def test_names_are_unique_per_department(self):
        department = make_department()
        make_shift_type(department, name="Night")
        with self.assertRaises(Exception):
            ShiftType.objects.create(
                department=department,
                name="Night",
                start_time=time(1, 0),
                end_time=time(2, 0),
                colour="#112233",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.ShiftTypeNightFlagTests -v 1`

Expected: FAIL with `ModuleNotFoundError: No module named 'shifts'` until the app exists, then import errors until the models exist. After creating the package, re-run this same command. It must fail on the model until Step 3, then pass in Step 4. Add `"shifts"` to `INSTALLED_APPS` before the re-run or Django will not discover the tests.

- [ ] **Step 3: Write the minimal implementation**

`shifts/apps.py`:

```python
from django.apps import AppConfig


class ShiftsConfig(AppConfig):
    name = "shifts"
```

`shifts/__init__.py` and `shifts/migrations/__init__.py` are empty.

`config/settings.py`: add `"shifts"` to `INSTALLED_APPS` after `"webpush"`.

`shifts/models.py`:

```python
from django.conf import settings
from django.core.exceptions import ValidationError
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
    colour = models.CharField(_("Colour"), max_length=7, default="#6366f1")
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
```

`shifts/admin.py`:

```python
from django.contrib import admin

from .models import ShiftAssignment, ShiftType


@admin.register(ShiftType)
class ShiftTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "start_time", "end_time", "is_night", "archived")
    list_filter = ("archived", "is_night", "department")


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "shift_type", "checked_in_at")
    list_filter = ("date", "shift_type__department")
```

Generate the migration after the models exist:

```bash
python manage.py makemigrations shifts --name initial
```

Then edit `shifts/migrations/0001_initial.py` so `dependencies` includes `("core", "0023_role_can_manage_shifts")` and `("accounts", "0008_alter_requires_password_change_verbose")` plus the swappable user dependency Django already inserts. Do not add `check_in_cleared_by`.

Create `shifts/urls.py` with `urlpatterns = []`. Do not add the include in `config/urls.py` until Task 4.

Create `shifts/forms.py` now, before any later task imports it:

```python
"""Shift forms. Task 5 replaces this module with ShiftTypeForm."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.ShiftTypeNightFlagTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts config/settings.py
git commit -m "Add shifts models and app scaffold"
```

## Task 3: Interval, hours, week, and overlap services

**Files:**
- Create: `shifts/services.py`
- Modify: `shifts/tests.py` (append classes only)

**Interfaces:**
- Consumes: `ShiftAssignment`, `ShiftType`.
- Produces these functions. Later tasks import them from `shifts.services` and must use these names.

```python
WORKER_HOURS_LOOKBACK_DAYS = 7
WORKER_HOURS_MAX_MINUTES = 16 * 60
CHECK_IN_EARLY_MINUTES = 30
NIGHT_ROTATION_LOOKBACK_DAYS = 14
REPEAT_WEEKS_MAX = 12

def saturday_of(day: date) -> date: ...
def normalize_start(day: date, view: str) -> date: ...
def week_dates(saturday: date) -> list[date]: ...
def month_dates(first: date) -> list[date]: ...
def effective_times(assignment) -> tuple[time, time]: ...
def effective_crosses_midnight(start_t: time, end_t: time) -> bool: ...
def interval_for(on: date, start_t: time, end_t: time) -> tuple[datetime, datetime]: ...
def effective_interval(assignment) -> tuple[datetime, datetime]: ...
def overlaps(left: tuple[datetime, datetime], right: tuple[datetime, datetime]) -> bool: ...
def clock_length(start_t: time, end_t: time) -> tuple[int, int]: ...
def clipped_day_night_minutes(assignment, range_start: datetime, range_end: datetime) -> tuple[int, int]: ...
def overrides_set_by_worker(assignment) -> bool: ...
def check_in_state(assignment, now: datetime) -> str: ...
```

`clock_length` returns `(total_minutes, after_midnight_minutes)`. `check_in_state` returns `"open"`, `"early"`, or `"closed"`.

- [ ] **Step 1: Write the failing test**

Append to `shifts/tests.py`:

```python
class WeekAndHoursTests(TestCase):
    def test_wednesday_snaps_to_previous_saturday(self):
        from shifts.services import normalize_start, saturday_of, week_dates

        wednesday = date(2026, 10, 7)  # Wednesday
        saturday = date(2026, 10, 3)
        self.assertEqual(saturday_of(wednesday), saturday)
        self.assertEqual(saturday_of(saturday), saturday)
        self.assertEqual(normalize_start(wednesday, "week"), saturday)
        self.assertEqual(normalize_start(date(2026, 10, 7), "month"), date(2026, 10, 1))
        self.assertEqual(week_dates(saturday)[0], saturday)
        self.assertEqual(week_dates(saturday)[-1], date(2026, 10, 9))  # Friday
        self.assertEqual(len(week_dates(saturday)), 7)

    def test_night_type_minutes_stay_night_when_clipped(self):
        from shifts.services import clipped_day_night_minutes, interval_for

        department = make_department("Hours")
        user = make_user("hana", "support", department)
        night = make_shift_type(department)
        friday = date(2026, 10, 9)
        row = make_assignment(user, night, friday)
        start, end = interval_for(friday, time(22, 0), time(6, 0))
        day, night_m = clipped_day_night_minutes(row, start, end)
        self.assertEqual((day, night_m), (0, 480))
        week_end = timezone.make_aware(datetime(2026, 10, 10, 0, 0))
        week_start = timezone.make_aware(datetime(2026, 10, 3, 0, 0))
        day, night_m = clipped_day_night_minutes(row, week_start, week_end)
        self.assertEqual((day, night_m), (0, 120))
        next_week_end = timezone.make_aware(datetime(2026, 10, 17, 0, 0))
        day, night_m = clipped_day_night_minutes(row, week_end, next_week_end)
        self.assertEqual((day, night_m), (0, 360))

    def test_same_evening_on_a_night_type_is_all_night_hours(self):
        from shifts.services import clipped_day_night_minutes

        department = make_department("Evening")
        user = make_user("omar", "support", department)
        night = make_shift_type(department, name="Night desk")
        row = make_assignment(user, night, date(2026, 10, 6), time(18, 0), time(23, 0))
        start = timezone.make_aware(datetime(2026, 10, 6, 0, 0))
        end = timezone.make_aware(datetime(2026, 10, 7, 0, 0))
        self.assertEqual(clipped_day_night_minutes(row, start, end), (0, 300))

    def test_day_type_crossing_midnight_stays_day_hours(self):
        from shifts.services import clipped_day_night_minutes, clock_length

        department = make_department("Day cross")
        user = make_user("lina", "support", department)
        day_type = make_shift_type(department, name="Days", start=time(9, 0), end=time(17, 0))
        row = make_assignment(user, day_type, date(2026, 10, 6), time(22, 0), time(6, 0))
        start = timezone.make_aware(datetime(2026, 10, 6, 0, 0))
        end = timezone.make_aware(datetime(2026, 10, 8, 0, 0))
        self.assertEqual(clipped_day_night_minutes(row, start, end), (480, 0))
        self.assertEqual(clock_length(time(22, 0), time(6, 0)), (480, 360))
        self.assertEqual(clock_length(time(9, 0), time(12, 30)), (210, 0))

    def test_half_open_touch_is_not_overlap(self):
        from shifts.services import interval_for, overlaps

        monday = date(2026, 10, 5)
        left = interval_for(monday, time(22, 0), time(6, 0))
        right = interval_for(date(2026, 10, 6), time(6, 0), time(14, 0))
        early = interval_for(date(2026, 10, 6), time(1, 0), time(9, 0))
        self.assertFalse(overlaps(left, right))
        self.assertTrue(overlaps(left, early))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.WeekAndHoursTests -v 1`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `shifts.services`.

- [ ] **Step 3: Write the minimal implementation**

Write `shifts/services.py` with this module. Import `is_shift_manager` inside `overrides_set_by_worker` to avoid a cycle. Task 4 creates `shifts/access.py`. Until then, put a temporary `is_shift_manager` in `shifts/access.py` in this same step (the full helper is Task 4; this stub must match the final signature):

```python
def is_shift_manager(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    role = getattr(user, "role", None)
    return bool(role and role.can_manage_shifts)
```

`shifts/services.py`:

```python
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from django.utils.timezone import NonExistentTimeError
from django.utils.translation import gettext as _

from shifts.access import is_shift_manager

WORKER_HOURS_LOOKBACK_DAYS = 7
WORKER_HOURS_MAX_MINUTES = 16 * 60
CHECK_IN_EARLY_MINUTES = 30
NIGHT_ROTATION_LOOKBACK_DAYS = 14
REPEAT_WEEKS_MAX = 12


def saturday_of(day: date) -> date:
    return day - timedelta(days=(day.weekday() - 5) % 7)


def normalize_start(day: date, view: str) -> date:
    if view == "month":
        return day.replace(day=1)
    return saturday_of(day)


def week_dates(saturday: date) -> list[date]:
    return [saturday + timedelta(days=offset) for offset in range(7)]


def month_dates(first: date) -> list[date]:
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1, day=1)
    else:
        nxt = first.replace(month=first.month + 1, day=1)
    days = (nxt - first).days
    return [first + timedelta(days=offset) for offset in range(days)]


def effective_times(assignment):
    if assignment.start_time_override and assignment.end_time_override:
        return assignment.start_time_override, assignment.end_time_override
    return assignment.shift_type.start_time, assignment.shift_type.end_time


def effective_crosses_midnight(start_t: time, end_t: time) -> bool:
    return end_t < start_t


def aware_on(on: date, clock: time):
    tz = timezone.get_current_timezone()
    try:
        return timezone.make_aware(datetime.combine(on, clock), tz)
    except NonExistentTimeError as exc:
        raise ValueError(_("That time does not exist on this date.")) from exc


def interval_for(on: date, start_t: time, end_t: time):
    start_dt = aware_on(on, start_t)
    end_day = on + timedelta(days=1) if effective_crosses_midnight(start_t, end_t) else on
    end_dt = aware_on(end_day, end_t)
    return start_dt, end_dt


def effective_interval(assignment):
    start_t, end_t = effective_times(assignment)
    return interval_for(assignment.date, start_t, end_t)


def overlaps(left, right) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def clock_length(start_t: time, end_t: time):
    if start_t == end_t:
        return 0, 0
    anchor = date(2026, 1, 5)
    start_dt, end_dt = interval_for(anchor, start_t, end_t)
    total = int((end_dt - start_dt).total_seconds() // 60)
    if effective_crosses_midnight(start_t, end_t):
        after = end_t.hour * 60 + end_t.minute
    else:
        after = 0
    return total, after


def clipped_day_night_minutes(assignment, range_start, range_end):
    start_dt, end_dt = effective_interval(assignment)
    clip_start = max(start_dt, range_start)
    clip_end = min(end_dt, range_end)
    if clip_end <= clip_start:
        return 0, 0
    minutes = int((clip_end - clip_start).total_seconds() // 60)
    if assignment.shift_type.is_night:
        return 0, minutes
    return minutes, 0


def overrides_set_by_worker(assignment) -> bool:
    if not assignment.start_time_override or not assignment.end_time_override:
        return False
    setter = assignment.times_set_by
    if setter is None:
        return False
    return not is_shift_manager(setter)


def check_in_state(assignment, now) -> str:
    start_dt, end_dt = effective_interval(assignment)
    opens = start_dt - timedelta(minutes=CHECK_IN_EARLY_MINUTES)
    if now < opens:
        return "early"
    if now >= end_dt:
        return "closed"
    return "open"


def neighbor_conflict(assignment, start_dt, end_dt, exclude_pk=None):
    from shifts.models import ShiftAssignment

    qs = ShiftAssignment.objects.filter(
        user_id=assignment.user_id,
        date__gte=assignment.date - timedelta(days=1),
        date__lte=assignment.date + timedelta(days=1),
    ).select_related("shift_type", "user")
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    proposed = (start_dt, end_dt)
    for other in qs:
        if overlaps(proposed, effective_interval(other)):
            return other
    return None


def overlap_message(other) -> str:
    start_t, end_t = effective_times(other)
    return _("This shift overlaps %(name)s on %(date)s (%(start)s–%(end)s).") % {
        "name": other.shift_type.name,
        "date": other.date.isoformat(),
        "start": start_t.strftime("%H:%M"),
        "end": end_t.strftime("%H:%M"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.WeekAndHoursTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/services.py shifts/access.py shifts/tests.py
git commit -m "Add shift interval and hours services"
```

## Task 4: Access, landing, shell, sidebar

**Files:**
- Modify: `shifts/access.py` (replace the stub if Task 3 wrote only `is_shift_manager`)
- Create: `shifts/urls.py` body, `templates/shifts/shell.html`, `static/css/shifts.css`, `static/js/shifts.js`
- Modify: `shifts/views.py` (create it), `config/urls.py`, `templates/base.html`, `static/js/app-shell.js`
- Test: `shifts/tests.py`

**Interfaces:**
- Consumes: `is_shift_manager(user) -> bool`.
- Produces:
  - `home_target(user) -> str` returns `"shifts_rota"`, `"shifts_mine"`, or `"shifts_available"`.
  - `shifts_home` GET redirects to that URL name. A logged-in user who is neither support nor branch and not a manager gets 403.
  - Shell root id `shifts-shell-pane`.

- [ ] **Step 1: Write the failing test**

```python
class LandingTests(TestCase):
    def test_each_role_lands_on_its_page(self):
        department = make_department("Land")
        manager_role = make_role(name="Shift lead", can_manage_shifts=True)
        manager = make_user("lead", "support", department, manager_role)
        support = make_user("agent", "support", department)
        branch = make_user("branch", "branch")
        self.client.force_login(manager)
        self.assertRedirects(self.client.get(reverse("shifts_home")), reverse("shifts_rota"))
        self.client.force_login(support)
        self.assertRedirects(self.client.get(reverse("shifts_home")), reverse("shifts_mine"))
        self.client.force_login(branch)
        self.assertRedirects(self.client.get(reverse("shifts_home")), reverse("shifts_available"))

    def test_sidebar_link_is_present_for_support(self):
        department = make_department("Nav")
        support = make_user("navagent", "support", department)
        self.client.force_login(support)
        response = self.client.get(reverse("shifts_mine"))
        self.assertContains(response, 'data-nav-key="shifts"')
```

The mine/rota/available views can return a shell with a heading in this task. Later tasks replace the body.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.LandingTests -v 1`

Expected: FAIL with `NoReverseMatch: 'shifts_home'`.

- [ ] **Step 3: Write the minimal implementation**

`shifts/access.py` final contents:

```python
def is_shift_manager(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    role = getattr(user, "role", None)
    return bool(role and role.can_manage_shifts)


def home_target(user) -> str:
    if is_shift_manager(user):
        return "shifts_rota"
    if getattr(user, "user_type", "") == "support":
        return "shifts_mine"
    if getattr(user, "user_type", "") == "branch":
        return "shifts_available"
    return ""


def display_name(user) -> str:
    full = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    return full or user.username
```

`shifts/views.py` starts with:

```python
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from shifts.access import home_target, is_shift_manager


def _forbid():
    return HttpResponseForbidden(_("You cannot open this page."))


@login_required
@require_GET
def shifts_home(request):
    target = home_target(request.user)
    if not target:
        return _forbid()
    return redirect(target)


@login_required
@require_GET
def shifts_rota(request):
    if not is_shift_manager(request.user):
        return _forbid()
    return render(request, "shifts/rota.html", {"shell_etag": ""})


@login_required
@require_GET
def shifts_mine(request):
    if request.user.user_type != "support" and not is_shift_manager(request.user):
        return _forbid()
    return render(request, "shifts/mine.html", {})


@login_required
@require_GET
def shifts_available(request):
    return render(request, "shifts/available.html", {})
```

`shifts/urls.py`:

```python
from django.urls import path

from shifts import views

urlpatterns = [
    path("", views.shifts_home, name="shifts_home"),
    path("rota/", views.shifts_rota, name="shifts_rota"),
    path("mine/", views.shifts_mine, name="shifts_mine"),
    path("available/", views.shifts_available, name="shifts_available"),
]
```

`config/urls.py`: `path("shifts/", include("shifts.urls")),` next to the other app includes.

`templates/shifts/shell.html`:

```html
{% extends "base.html" %}
{% load i18n static %}
{% block extra_head %}{{ block.super }}<link rel="stylesheet" href="{% static 'css/shifts.css' %}">{% endblock %}
{% block content %}
<script>
(function () {
  var drop = ["ticket-detail-page", "kb-page", "kb-search-page", "kb-detail-page", "kb-form-page", "settings-page", "dashboard-page"];
  drop.forEach(function (cls) { document.body.classList.remove(cls); });
  if (window.updateActiveNav) window.updateActiveNav();
})();
</script>
<div id="shifts-shell-pane" class="shifts-page" data-etag="{{ shell_etag|default:'' }}">
  <nav class="settings-tabs" role="tablist">
    {% if is_manager %}
    <a class="settings-tab" role="tab" tabindex="0"
       aria-selected="{% if request.resolver_match.url_name == 'shifts_rota' %}true{% else %}false{% endif %}"
       href="{% url 'shifts_rota' %}"
       hx-get="{% url 'shifts_rota' %}"
       hx-target="#shell-content"
       hx-swap="innerHTML show:window:top settle:0"
       hx-push-url="true"
       hx-sync="#shell-content:replace"
       onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); window.htmx.trigger(this, 'click');}">{% trans "Rota" %}</a>
    {# Task 5: Shift types tab goes here, still inside is_manager. #}
    {# Task 9: Calculator tab goes here, after Shift types and before Available now. #}
    <a class="settings-tab" role="tab" tabindex="0"
       aria-selected="{% if request.resolver_match.url_name == 'shifts_available' %}true{% else %}false{% endif %}"
       href="{% url 'shifts_available' %}"
       hx-get="{% url 'shifts_available' %}"
       hx-target="#shell-content"
       hx-swap="innerHTML show:window:top settle:0"
       hx-push-url="true"
       hx-sync="#shell-content:replace"
       onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); window.htmx.trigger(this, 'click');}">{% trans "Available now" %}</a>
    {% endif %}
    {% if user.user_type == "support" or is_manager %}
    <a class="settings-tab" role="tab" tabindex="0"
       aria-selected="{% if request.resolver_match.url_name == 'shifts_mine' %}true{% else %}false{% endif %}"
       href="{% url 'shifts_mine' %}"
       hx-get="{% url 'shifts_mine' %}"
       hx-target="#shell-content"
       hx-swap="innerHTML show:window:top settle:0"
       hx-push-url="true"
       hx-sync="#shell-content:replace"
       onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); window.htmx.trigger(this, 'click');}">{% trans "My shifts" %}</a>
    {# Task 12: Team rota tab goes here, still inside support or manager. #}
    {% endif %}
    {% if not is_manager %}
    <a class="settings-tab" role="tab" tabindex="0"
       aria-selected="{% if request.resolver_match.url_name == 'shifts_available' %}true{% else %}false{% endif %}"
       href="{% url 'shifts_available' %}"
       hx-get="{% url 'shifts_available' %}"
       hx-target="#shell-content"
       hx-swap="innerHTML show:window:top settle:0"
       hx-push-url="true"
       hx-sync="#shell-content:replace"
       onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); window.htmx.trigger(this, 'click');}">{% trans "Available now" %}</a>
    {% endif %}
  </nav>
  {% block shifts_body %}{% endblock %}
</div>
{% endblock %}
{% block extra_js %}{{ block.super }}<script src="{% static 'js/shifts.js' %}"></script>{% endblock %}
```

The two Available now links are mutually exclusive. A manager sees the one inside `{% if is_manager %}`, after Rota and before My shifts. A non-manager sees only the one inside `{% if not is_manager %}`. Do not render both. Finished order: manager is Rota, Shift types, Calculator, Available now, My shifts, Team rota. Support who is not a manager is My shifts, Team rota, Available now. A branch user sees Available now only. Later tasks insert a tab at the comment that names that task. Each new tab repeats the `hx-get` / `hx-target="#shell-content"` / `hx-swap="innerHTML show:window:top settle:0"` / `hx-push-url="true"` / `hx-sync="#shell-content:replace"` / `tabindex="0"` / `onkeydown` attributes. Do not set `hx-trigger="shell-nav"` on a tab. Pass `is_manager` from a tiny context helper used by every shifts render:

```python
def _shell(request, template, context):
    context["is_manager"] = is_shift_manager(request.user)
    return render(request, template, context)
```

`rota.html`, `mine.html`, and `available.html` each `{% extends "shifts/shell.html" %}` and fill `shifts_body` with an `h1` only, until later tasks. Do not put a second body-class script in those pages. The shell script above is the only one.

`static/css/shifts.css` (only this file for shifts rules). No `left`, `right`, `margin-left`, or `margin-right`.

```css
#shifts-shell-pane .shifts-grid-wrap { overflow-x: auto; }
#shifts-shell-pane .shifts-person {
  position: sticky;
  inset-inline-start: 0;
  background: var(--panel-bg, #fff);
}
#shifts-shell-pane .shifts-cell--night {
  outline: 2px dashed var(--warning, #fbbf24);
}
#shifts-shell-pane .shifts-gap {
  background: color-mix(in srgb, var(--danger, #f87171) 25%, transparent);
}
#shifts-shell-pane .shifts-cell-btn { min-block-size: 44px; }
#shifts-shell-pane .shifts-toolbar { display: flex; flex-wrap: wrap; gap: 0.5rem; }
#shifts-shell-pane .shifts-cards { display: flex; flex-wrap: wrap; gap: 1rem; }
@media (max-width: 720px) {
  #shifts-shell-pane .shifts-toolbar select { inline-size: 100%; }
  #shifts-shell-pane .shifts-cards { flex-direction: column; }
}
```

`static/js/shifts.js`:

```javascript
document.body.addEventListener("htmx:configRequest", function (evt) {
  var elt = evt.detail.elt;
  if (!elt || elt.id !== "shifts-available-now") return;
  var etag = elt.getAttribute("data-etag");
  if (etag) evt.detail.headers["If-None-Match"] = etag;
});
document.body.addEventListener("htmx:beforeSwap", function (evt) {
  var target = evt.detail.target;
  if (!target || target.id !== "shifts-available-now") return;
  var xhr = evt.detail.xhr;
  if (xhr && xhr.status === 304) {
    evt.detail.shouldSwap = false;
    evt.detail.isError = false;
  }
});
document.addEventListener("visibilitychange", function () {
  if (document.hidden) return;
  var board = document.getElementById("shifts-available-now");
  if (board && window.htmx) window.htmx.trigger(board, "refresh");
});
```

Add `refresh` to the board trigger in Task 13: `every 20s [!document.hidden], refresh`.

Sidebar in `templates/base.html`, after the Knowledge Base `</a>` and before Dashboard:

```html
{% if user.is_superuser or user.role.can_manage_shifts or user.user_type == 'support' or user.user_type == 'branch' %}
<a href="{% url 'shifts_home' %}"
   data-nav-key="shifts"
   {% if user.is_authenticated %}data-shell-nav="1"
   hx-get="{% url 'shifts_home' %}"
   hx-target="#shell-content"
   hx-swap="innerHTML show:window:top settle:0"
   hx-push-url="true"
   hx-trigger="shell-nav"
   hx-sync="#shell-content:replace"{% endif %}
   {% if '/shifts/' in request.path or request.path == '/shifts' %}class="active" aria-current="page"{% endif %}>{% trans "Shifts" %}</a>
{% endif %}
```

`static/js/app-shell.js` only these edits:

1. In `updateActiveNav`, before the tickets check: `else if (path === "/shifts" || path.indexOf("/shifts/") === 0) key = "shifts";`
2. In `shellPageKindFromHtml` and `shellPageKindFromDom`, if the HTML or DOM contains `id="shifts-shell-pane"`, return `"shifts"`.
3. In `shellPaneEtag`’s `ids` object, add `shifts: "shifts-shell-pane"`.

Do not add a skeleton to `base.html`. Do not change `#tickets-live`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.LandingTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/access.py shifts/views.py shifts/urls.py shifts/tests.py config/urls.py templates/shifts templates/base.html static/css/shifts.css static/js/shifts.js static/js/app-shell.js
git commit -m "Add shifts shell, landing, and sidebar link"
```

## Task 5: Shift types

**Files:**
- Modify: `shifts/forms.py`, `shifts/views.py`, `shifts/urls.py`
- Create: `templates/shifts/types.html`, `templates/shifts/type_form.html`
- Test: `shifts/tests.py`

**Interfaces:**
- Consumes: `is_shift_manager`, `ShiftType`.
- Produces: `shifts_types`, `shifts_type_add`, `shifts_type_edit`, `shifts_type_archive`. Archive sets `archived=True`. No delete view.

- [ ] **Step 1: Write the failing test**

```python
class ShiftTypeCrudTests(TestCase):
    def test_support_cannot_open_types(self):
        department = make_department("Types")
        support = make_user("types-agent", "support", department)
        self.client.force_login(support)
        self.assertEqual(self.client.get(reverse("shifts_types")).status_code, 403)

    def test_manager_creates_and_archives(self):
        department = make_department("Types2")
        role = make_role("Types lead", can_manage_shifts=True)
        manager = make_user("types-lead", "support", department, role)
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_type_add"), {
            "department": department.pk,
            "name": "Night",
            "start_time": "22:00",
            "end_time": "06:00",
            "colour": "#336699",
        })
        self.assertEqual(response.status_code, 200)
        row = ShiftType.objects.get(name="Night")
        self.assertTrue(row.is_night)
        archive = self.client.post(reverse("shifts_type_archive", args=[row.pk]))
        self.assertEqual(archive.status_code, 302)
        row.refresh_from_db()
        self.assertTrue(row.archived)

    def test_equal_times_rejected(self):
        department = make_department("Types3")
        role = make_role("Types lead 2", can_manage_shifts=True)
        manager = make_user("types-lead-2", "support", department, role)
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_type_add"), {
            "department": department.pk,
            "name": "Bad",
            "start_time": "09:00",
            "end_time": "09:00",
            "colour": "#336699",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShiftType.objects.filter(name="Bad").exists())
        self.assertContains(response, "Start and end must differ.")

    def test_short_name_rejected(self):
        department = make_department("Types4")
        role = make_role("Types lead 3", can_manage_shifts=True)
        manager = make_user("types-lead-3", "support", department, role)
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_type_add"), {
            "department": department.pk,
            "name": " N ",
            "start_time": "09:00",
            "end_time": "17:00",
            "colour": "#336699",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShiftType.objects.filter(department=department).exists())
        self.assertContains(response, "at least 2 characters")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.ShiftTypeCrudTests -v 1`

Expected: FAIL with `NoReverseMatch: 'shifts_types'`.

- [ ] **Step 3: Write the minimal implementation**

Replace the Task 2 placeholder `shifts/forms.py` with:

```python
import re

from django import forms
from django.utils.translation import gettext_lazy as _

from shifts.models import ShiftType

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ShiftTypeForm(forms.ModelForm):
    class Meta:
        model = ShiftType
        fields = ["department", "name", "start_time", "end_time", "colour", "archived"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields.pop("archived")

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError(_("Shift type name must be at least 2 characters long."))
        return name.strip()

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and start == end:
            self.add_error("end_time", _("Start and end must differ."))
        colour = cleaned.get("colour") or ""
        if colour and not _HEX.match(colour):
            self.add_error("colour", _("Colour must be a 6-digit hex value."))
        return cleaned
```

Append to `shifts/views.py`. `is_night` is set by `ShiftType.save()`, not by the form.

```python
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST

from core.models import Department
from shifts.forms import ShiftTypeForm
from shifts.models import ShiftType


def _selected_department(request):
    raw = request.POST.get("department") or request.GET.get("department")
    if raw:
        return get_object_or_404(Department, pk=raw)
    department = Department.objects.order_by("name").first()
    if department is None:
        raise Http404(_("No department exists."))
    return department


@login_required
@require_http_methods(["GET", "POST"])
def shifts_type_add(request):
    if not is_shift_manager(request.user):
        return _forbid()
    form = ShiftTypeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return shifts_types(request)
    return render(request, "shifts/type_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def shifts_type_edit(request, pk):
    if not is_shift_manager(request.user):
        return _forbid()
    row = get_object_or_404(ShiftType, pk=pk)
    form = ShiftTypeForm(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        form.save()
        return shifts_types(request)
    return render(request, "shifts/type_form.html", {"form": form, "editing": True})


@login_required
@require_POST
def shifts_type_archive(request, pk):
    if not is_shift_manager(request.user):
        return _forbid()
    row = get_object_or_404(ShiftType, pk=pk)
    row.archived = True
    row.save()
    return redirect("shifts_types")


@login_required
@require_GET
def shifts_types(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    rows = (
        ShiftType.objects.filter(department=department)
        .select_related("department")
        .order_by("archived", "name")
    )
    return _shell(request, "shifts/types.html", {
        "department": department,
        "types": rows,
        "departments": Department.objects.order_by("name"),
    })
```

`require_GET` is already imported in Task 4. Add `require_http_methods` and `require_POST` to that import.

Append to `shifts/urls.py`:

```python
path("types/", views.shifts_types, name="shifts_types"),
path("types/add/", views.shifts_type_add, name="shifts_type_add"),
path("types/<int:pk>/edit/", views.shifts_type_edit, name="shifts_type_edit"),
path("types/<int:pk>/archive/", views.shifts_type_archive, name="shifts_type_archive"),
```

`templates/shifts/type_form.html`. The test client posts without HTMX and reads the error text from `form.as_p`. Every POST form includes `{% csrf_token %}`, matching `templates/news/form_partial.html`. This project has no global HTMX CSRF header.

```html
{% load i18n %}
<form method="post" hx-post="." hx-target="#modal-content">
  {% csrf_token %}
  {{ form.as_p }}
  <p class="help">{% trans "A shift that ends before its start is a night shift and runs into the next morning." %}</p>
  <button class="btn primary" type="submit">{% trans "Save" %}</button>
</form>
```

Archive in `types.html` is its own POST form:

```html
<form method="post" action="{% url 'shifts_type_archive' row.pk %}">
  {% csrf_token %}
  <button class="btn secondary" type="submit">{% trans "Archive" %}</button>
</form>
```

Buttons that open the form use `hx-get`, `hx-target="#modal-content"`, and `onclick="openModal()"`, matching `templates/core/management/list_partial_v2.html`. Clearing the archived checkbox on edit and saving is the only restore path. There is no delete view.

Inside `{% if is_manager %}`, immediately after the Rota link and before the manager Available now link, insert:

```html
<a class="settings-tab" role="tab" tabindex="0"
   aria-selected="{% if request.resolver_match.url_name == 'shifts_types' %}true{% else %}false{% endif %}"
   href="{% url 'shifts_types' %}"
   hx-get="{% url 'shifts_types' %}"
   hx-target="#shell-content"
   hx-swap="innerHTML show:window:top settle:0"
   hx-push-url="true"
   hx-sync="#shell-content:replace"
   onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); window.htmx.trigger(this, 'click');}">{% trans "Shift types" %}</a>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.ShiftTypeCrudTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/forms.py shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/types.html templates/shifts/type_form.html templates/shifts/shell.html
git commit -m "Add shift type management"
```

## Task 6: Rota grid, cell modal, ETag

**Files:**
- Modify: `shifts/views.py`, `shifts/urls.py`, `shifts/tests.py`
- Create: `templates/shifts/rota.html`, `templates/shifts/rota_grid.html`, `templates/shifts/cell_form.html`

**Interfaces:**
- Consumes: `normalize_start`, `week_dates`, `month_dates`, `effective_times`, `effective_interval`, `neighbor_conflict`, `overlap_message`, `overrides_set_by_worker`.
- Produces: `shifts_rota` GET query `view` and `start` and `department`. `shifts_rota_grid` GET. `shifts_cell` GET/POST. Grid id `shifts-rota-grid`.

- [ ] **Step 1: Write the failing test**

```python
class RotaGridTests(TestCase):
    def setUp(self):
        self.department = make_department("Rota")
        self.role = make_role("Rota lead", can_manage_shifts=True)
        self.manager = make_user("rota-lead", "support", self.department, self.role)
        self.agent = make_user("rota-agent", "support", self.department)
        self.night = make_shift_type(self.department)
        self.client.force_login(self.manager)

    def test_week_query_normalizes_to_saturday(self):
        response = self.client.get(reverse("shifts_rota"), {"view": "week", "start": "2026-10-07", "department": self.department.pk})
        self.assertContains(response, "2026-10-03")
        self.assertContains(response, "2026-10-09")

    def test_cell_post_blocks_overlap(self):
        make_assignment(self.agent, self.night, date(2026, 10, 5))
        response = self.client.post(reverse("shifts_cell"), {
            "user": self.agent.pk,
            "date": "2026-10-06",
            "department": self.department.pk,
            "shift_type": self.night.pk,
            "start_time_override": "01:00",
            "end_time_override": "09:00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "overlaps")
        self.assertEqual(ShiftAssignment.objects.filter(user=self.agent).count(), 1)

    def test_support_gets_403(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("shifts_rota")).status_code, 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.RotaGridTests -v 1`

Expected: FAIL. The rota page from Task 4 does not contain the Saturday date, and `shifts_cell` is missing.

- [ ] **Step 3: Write the minimal implementation**

Replace the Task 4 `shifts_rota` stub with the functions below. Do not call `QuerySet.union()`. Merge the two user querysets in Python.

```python
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Max
from django.utils.translation import get_language

from core.http_cache import apply_read_etag, etag_digest, htmx_not_modified, htmx_revalidation_match
from shifts.access import display_name
from shifts.models import ShiftAssignment, ShiftType
from shifts.services import (
    effective_times,
    interval_for,
    month_dates,
    neighbor_conflict,
    normalize_start,
    overlap_message,
    overrides_set_by_worker,
    week_dates,
)

User = get_user_model()


def _rota_dates(request):
    view = request.POST.get("view") or request.GET.get("view") or "week"
    if view not in ("week", "month"):
        view = "week"
    raw = request.POST.get("start") or request.GET.get("start")
    day = date.fromisoformat(raw) if raw else timezone.localdate()
    start = normalize_start(day, view)
    dates = month_dates(start) if view == "month" else week_dates(start)
    return view, start, dates


def _rota_bundle(department, dates):
    first, last = dates[0], dates[-1]
    assignments = list(
        ShiftAssignment.objects.filter(
            shift_type__department=department,
            date__gte=first - timedelta(days=1),
            date__lte=last,
        ).select_related("user", "shift_type", "times_set_by", "times_set_by__role")
    )
    visible = [row for row in assignments if first <= row.date <= last]
    assigned_ids = {row.user_id for row in visible}
    active = User.objects.filter(
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ).only("id", "username", "first_name", "last_name", "department_id", "user_type", "status")
    extra = User.objects.filter(pk__in=assigned_ids).only(
        "id", "username", "first_name", "last_name", "department_id", "user_type", "status"
    )
    people = {row.pk: row for row in list(active) + list(extra)}
    ordered = sorted(people.values(), key=lambda row: ((row.first_name or ""), row.username))
    by_key = {(row.user_id, row.date): row for row in visible}
    return {
        "assignments": assignments,
        "people": ordered,
        "by_key": by_key,
        "dates": dates,
    }


def _rota_etag(department, view, start, assignments):
    max_assignment = max((row.updated_at for row in assignments), default=None)
    max_type = (
        ShiftType.objects.filter(department=department).aggregate(m=Max("updated_at"))["m"]
    )
    return etag_digest([
        get_language(),
        department.pk,
        view,
        start.isoformat(),
        len(assignments),
        max_assignment.isoformat() if max_assignment else "",
        max_type.isoformat() if max_type else "",
    ])


def _grid_response(request, department, retarget=False, notice="", skips=None, error=""):
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    etag = _rota_etag(department, view, start, bundle["assignments"])
    if not retarget and htmx_revalidation_match(request, etag):
        return htmx_not_modified(etag)
    context = {
        **bundle,
        "department": department,
        "departments": Department.objects.order_by("name"),
        "view": view,
        "start": start,
        "readonly": False,
        "shell_etag": etag,
        "now": timezone.now(),
        "notice": notice,
        "skips": skips or [],
        "error": error,
    }
    template = "shifts/rota_grid.html" if retarget else "shifts/rota.html"
    response = _shell(request, template, context)
    if retarget:
        response["HX-Retarget"] = "#shifts-rota-grid"
        response["HX-Reswap"] = "outerHTML"
    return apply_read_etag(response, etag, request)


@login_required
@require_GET
def shifts_rota(request):
    if not is_shift_manager(request.user):
        return _forbid()
    return _grid_response(request, _selected_department(request), retarget=False)


@login_required
@require_GET
def shifts_rota_grid(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    etag = _rota_etag(department, view, start, bundle["assignments"])
    if htmx_revalidation_match(request, etag):
        return htmx_not_modified(etag)
    response = render(request, "shifts/rota_grid.html", {
        **bundle,
        "department": department,
        "view": view,
        "start": start,
        "readonly": False,
    })
    return apply_read_etag(response, etag, request)
```

`rota.html` extends the shell, shows the Saturday–Friday label as `{{ dates.0|date:"Y-m-d" }}`–`{{ dates|last|date:"Y-m-d" }}` (so the week test finds `2026-10-03` and `2026-10-09`), and includes `rota_grid.html`. The grid root is `<div id="shifts-rota-grid">`. Previous and next in week view add or subtract 7 days from `start`. Month view steps one month and does not snap to Saturday. Omit Copy, Repeat, and Auto-fill buttons until Tasks 7 and 8 register those URL names.

`rota_grid.html` loops `people` then `dates`. An empty manager cell is a button whose accessible name is `{{ person }} {{ day|date:"Y-m-d" }} {% trans "Empty" %}`. A filled cell uses `style="background-color: {{ cell.shift_type.colour }}"`, the type name, class `shifts-cell--night` and the word `{% trans "Night" %}` when `cell.shift_type.is_night`, `{% trans "Set by worker" %}` when `overrides_set_by_worker(cell)`, `{% trans "Archived" %}` when the type is archived, `{% trans "Not in this department" %}` when the date is today or later and `cell.user.department_id != department.pk`, and `{% trans "Inactive" %}` when the department matches but the user is not active. Show override times only when both overrides are set. The person `<th>` uses class `shifts-person`. Read-only grids (`readonly`) render text, not buttons. Check-in markers are Task 11. Do not set `request.ticket_list_304_defer_session_save` on these GETs.

Cell modal. Append:

```python
def _parse_clock(raw):
    if not raw:
        return None
    return time.fromisoformat(raw)


@login_required
@require_http_methods(["GET", "POST"])
def shifts_cell(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    user = get_object_or_404(User, pk=request.POST.get("user") or request.GET.get("user"))
    on = date.fromisoformat(request.POST.get("date") or request.GET.get("date"))
    existing = (
        ShiftAssignment.objects.filter(user=user, date=on)
        .select_related("shift_type")
        .first()
    )
    if request.method == "GET":
        return render(request, "shifts/cell_form.html", {
            "department": department,
            "person": user,
            "on": on,
            "existing": existing,
            "types": ShiftType.objects.filter(department=department, archived=False),
        })
    shift_type_id = request.POST.get("shift_type") or ""
    if not shift_type_id:
        if existing:
            existing.delete()
        response = _grid_response(request, department, retarget=True)
        response["HX-Trigger"] = "closeModal"
        return response
    shift_type = get_object_or_404(ShiftType, pk=shift_type_id, department=department)
    if request.POST.get("reset_times") == "1" and existing:
        existing.start_time_override = None
        existing.end_time_override = None
        existing.times_set_by = None
        existing.times_set_at = None
        existing.save()
        response = _grid_response(request, department, retarget=True)
        response["HX-Trigger"] = "closeModal"
        return response
    start_t = _parse_clock(request.POST.get("start_time_override"))
    end_t = _parse_clock(request.POST.get("end_time_override"))
    error = None
    if (start_t is None) ^ (end_t is None):
        error = _("Enter both start and end, or leave both blank.")
    elif start_t and end_t and start_t == end_t:
        error = _("Start and end must differ.")
    else:
        changing_user = existing is None or existing.user_id != user.pk
        if on >= timezone.localdate() or changing_user:
            if (
                user.user_type != User.UserType.SUPPORT
                or user.status != User.Status.ACTIVE
                or user.department_id != shift_type.department_id
            ):
                error = _("Only active support users in this department can be assigned.")
        if error is None and on >= timezone.localdate() and shift_type.archived:
            error = _("Archived shift types cannot be assigned.")
    if error is None:
        use_start = start_t or shift_type.start_time
        use_end = end_t or shift_type.end_time
        probe = existing or ShiftAssignment(user=user, date=on, shift_type=shift_type)
        try:
            start_dt, end_dt = interval_for(on, use_start, use_end)
        except ValueError as exc:
            error = str(exc)
        else:
            other = neighbor_conflict(probe, start_dt, end_dt, exclude_pk=getattr(existing, "pk", None))
            if other:
                error = overlap_message(other)
    if error:
        return render(request, "shifts/cell_form.html", {
            "department": department,
            "person": user,
            "on": on,
            "existing": existing,
            "types": ShiftType.objects.filter(department=department, archived=False),
            "error": error,
        })
    row = existing or ShiftAssignment(user=user, date=on)
    was_day = bool(existing and not existing.shift_type.is_night)
    row.shift_type = shift_type
    if start_t and end_t:
        row.start_time_override = start_t
        row.end_time_override = end_t
        row.times_set_by = request.user
        row.times_set_at = timezone.now()
    if was_day and shift_type.is_night:
        row.checked_in_at = None
    row.save()
    response = _grid_response(request, department, retarget=True)
    response["HX-Trigger"] = "closeModal"
    return response
```

`templates/shifts/cell_form.html`. The overlap test finds the word `overlaps` in `error`. The grid opens it with `hx-get="{% url 'shifts_cell' %}?user={{ person.pk }}&date={{ day|date:'Y-m-d' }}&department={{ department.pk }}" hx-target="#modal-content" onclick="openModal()"`.

```html
{% load i18n %}
<form method="post" action="{% url 'shifts_cell' %}" hx-post="{% url 'shifts_cell' %}" hx-target="#modal-content">
  {% csrf_token %}
  <input type="hidden" name="user" value="{{ person.pk }}">
  <input type="hidden" name="date" value="{{ on|date:'Y-m-d' }}">
  <input type="hidden" name="department" value="{{ department.pk }}">
  {% if error %}<p class="notice notice-error">{{ error }}</p>{% endif %}
  <label for="shift-type">{% trans "Shift type" %}</label>
  <select id="shift-type" name="shift_type">
    <option value="">{% trans "Clear" %}</option>
    {% for row in types %}
    <option value="{{ row.pk }}"{% if existing and existing.shift_type_id == row.pk %} selected{% endif %}>{{ row.name }}</option>
    {% endfor %}
  </select>
  <label for="start-override">{% trans "Start override" %}</label>
  <input id="start-override" type="time" name="start_time_override" value="{{ existing.start_time_override|time:'H:i' }}">
  <label for="end-override">{% trans "End override" %}</label>
  <input id="end-override" type="time" name="end_time_override" value="{{ existing.end_time_override|time:'H:i' }}">
  <button class="btn primary" type="submit">{% trans "Save" %}</button>
  {% if existing %}
  <button class="btn secondary" type="submit" name="reset_times" value="1">{% trans "Reset to shift default" %}</button>
  {% endif %}
  {% if existing and existing.checked_in_at and not existing.shift_type.is_night %}
  <button class="btn secondary" type="submit" name="clear_check_in" value="1">{% trans "Clear check-in" %}</button>
  {% endif %}
</form>
```

Empty `shift_type` clears the assignment. `reset_times=1` keeps the row and clears overrides. `clear_check_in=1` is handled in Task 11 and does not delete the row. Changing times does not clear `checked_in_at`. The save path above clears `checked_in_at` only when the previous type was a day type and the new type is a night type.

Append:

```python
path("rota/grid/", views.shifts_rota_grid, name="shifts_rota_grid"),
path("cell/", views.shifts_cell, name="shifts_cell"),
```

Add this test method to `RotaGridTests` before running Step 4. Six filled cells must stay inside the budget, which fails if the template queries once per cell:

```python
def test_grid_query_budget(self):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    for index in range(6):
        person = make_user(f"budget-{index}", "support", self.department)
        make_assignment(person, self.night, date(2026, 10, 5))
    with CaptureQueriesContext(connection) as captured:
        response = self.client.get(reverse("shifts_rota_grid"), {
            "view": "week",
            "start": "2026-10-03",
            "department": self.department.pk,
        })
    self.assertEqual(response.status_code, 200)
    self.assertLessEqual(len(captured), 12)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.RotaGridTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/rota.html templates/shifts/rota_grid.html templates/shifts/cell_form.html
git commit -m "Add rota grid and cell editor"
```

## Task 7: Copy last week and repeat forward

**Files:**
- Modify: `shifts/services.py`, `shifts/views.py`, `shifts/urls.py`, `templates/shifts/rota.html`, `shifts/tests.py`

**Interfaces:**
- Consumes: `REPEAT_WEEKS_MAX`, `overrides_set_by_worker`, `neighbor_conflict`, `week_dates`.
- Produces: `plan_copy(source_rows, day_shift, acting_user) -> list[dict]` and views `shifts_copy_week`, `shifts_repeat_week`.

Each planned row is `{"user_id", "date", "shift_type_id", "start", "end", "times_set_by_id", "times_set_at"}`. Worker-entered source rows have null overrides and null audit. Manager-set source rows copy the override times and set `times_set_by` to `acting_user`. `checked_in_at` is always null. Skip reasons are the strings `"archived shift type"`, `"already assigned"`, and `"overlaps"`.

- [ ] **Step 1: Write the failing test**

```python
class CopyWeekTests(TestCase):
    def test_worker_times_are_not_copied(self):
        from shifts.services import plan_copy

        department = make_department("Copy")
        agent = make_user("copy-agent", "support", department)
        manager = make_user("copy-lead", "support", department, make_role("Copy lead", can_manage_shifts=True))
        night = make_shift_type(department)
        source = make_assignment(agent, night, date(2026, 10, 3), time(18, 0), time(23, 0))
        planned = plan_copy([source], timedelta(days=7), manager)
        self.assertEqual(planned[0]["start"], None)
        self.assertEqual(planned[0]["end"], None)
        self.assertIsNone(planned[0]["times_set_by_id"])
        self.assertEqual(planned[0]["date"], date(2026, 10, 10))

    def test_repeat_rejects_13(self):
        department = make_department("Repeat")
        manager = make_user("repeat-lead", "support", department, make_role("Repeat lead", can_manage_shifts=True))
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_repeat_week"), {
            "department": department.pk,
            "start": "2026-10-03",
            "weeks": "13",
        })
        self.assertContains(response, "1 to 12")
        self.assertEqual(ShiftAssignment.objects.count(), 0)

    def test_friday_tail_does_not_become_saturday(self):
        department = make_department("Tail")
        manager = make_user("tail-lead", "support", department, make_role("Tail lead", can_manage_shifts=True))
        agent = make_user("tail-agent", "support", department)
        night = make_shift_type(department, name="Tail night")
        make_assignment(agent, night, date(2026, 10, 9))  # Friday
        self.client.force_login(manager)
        self.client.post(reverse("shifts_copy_week"), {
            "department": department.pk,
            "start": "2026-10-10",
        })
        self.assertFalse(ShiftAssignment.objects.filter(user=agent, date=date(2026, 10, 10)).exists())
        copied = ShiftAssignment.objects.get(user=agent, date=date(2026, 10, 16))
        self.assertIsNone(copied.checked_in_at)
        self.assertIsNone(copied.start_time_override)

    def test_manager_set_override_is_copied_and_repeated(self):
        department = make_department("Mgr copy")
        manager = make_user("mgr-copy-lead", "support", department, make_role("Mgr copy lead", can_manage_shifts=True))
        agent = make_user("mgr-copy-agent", "support", department)
        night = make_shift_type(department, name="Mgr night")
        source = make_assignment(agent, night, date(2026, 10, 3), time(18, 0), time(23, 0))
        source.times_set_by = manager
        source.save()
        self.client.force_login(manager)
        self.client.post(reverse("shifts_copy_week"), {
            "department": department.pk,
            "start": "2026-10-10",
        })
        copied = ShiftAssignment.objects.get(user=agent, date=date(2026, 10, 10))
        self.assertEqual(copied.start_time_override, time(18, 0))
        self.assertEqual(copied.end_time_override, time(23, 0))
        self.assertEqual(copied.times_set_by_id, manager.pk)
        self.client.post(reverse("shifts_repeat_week"), {
            "department": department.pk,
            "start": "2026-10-10",
            "weeks": "1",
        })
        repeated = ShiftAssignment.objects.get(user=agent, date=date(2026, 10, 17))
        self.assertEqual(repeated.start_time_override, time(18, 0))
        self.assertEqual(repeated.end_time_override, time(23, 0))
        self.assertEqual(repeated.times_set_by_id, manager.pk)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.CopyWeekTests -v 1`

Expected: FAIL with `ImportError` for `plan_copy`.

- [ ] **Step 3: Write the minimal implementation**

```python
def plan_copy(source_rows, day_shift, acting_user):
    planned = []
    for source in source_rows:
        item = {
            "user_id": source.user_id,
            "date": source.date + day_shift,
            "shift_type_id": source.shift_type_id,
            "start": None,
            "end": None,
            "times_set_by_id": None,
            "times_set_at": None,
            "skip": None,
        }
        if source.shift_type.archived:
            item["skip"] = "archived shift type"
        elif not overrides_set_by_worker(source) and source.start_time_override and source.end_time_override:
            item["start"] = source.start_time_override
            item["end"] = source.end_time_override
            item["times_set_by_id"] = acting_user.pk
            item["times_set_at"] = timezone.now()
        planned.append(item)
    return planned
```

`plan_copy` only shifts each source row’s date. A Friday 22:00–06:00 row moves to the next Friday. It does not create a Saturday row for the hours after midnight.

Append the views. Both are manager-only POSTs. Copy loads the previous Saturday–Friday (`start - 7 days` through `start - 1 day`) and calls `plan_copy(..., timedelta(days=7), request.user)`. Repeat parses `weeks`. Outside 1–12 it returns HTTP 200 and `"Enter a number of weeks from 1 to 12."` with no writes. For `k` in `1..N` it calls `plan_copy` with `timedelta(days=7 * k)` on the displayed Saturday–Friday rows, including rows created earlier in the same transaction, in Saturday-to-Friday order.

```python
from django.db import transaction

from shifts.services import REPEAT_WEEKS_MAX, plan_copy


def _write_planned(planned):
    created = 0
    skips = []
    for item in sorted(planned, key=lambda row: row["date"]):
        if item["skip"]:
            skips.append(item)
            continue
        if ShiftAssignment.objects.filter(user_id=item["user_id"], date=item["date"]).exists():
            item["skip"] = "already assigned"
            skips.append(item)
            continue
        shift_type = ShiftType.objects.get(pk=item["shift_type_id"])
        probe = ShiftAssignment(user_id=item["user_id"], date=item["date"], shift_type=shift_type)
        start_t = item["start"] or shift_type.start_time
        end_t = item["end"] or shift_type.end_time
        start_dt, end_dt = interval_for(item["date"], start_t, end_t)
        other = neighbor_conflict(probe, start_dt, end_dt)
        if other:
            item["skip"] = "overlaps"
            skips.append(item)
            continue
        ShiftAssignment.objects.create(
            user_id=item["user_id"],
            date=item["date"],
            shift_type=shift_type,
            start_time_override=item["start"],
            end_time_override=item["end"],
            times_set_by_id=item["times_set_by_id"],
            times_set_at=item["times_set_at"],
            checked_in_at=None,
        )
        created += 1
    return created, skips


@login_required
@require_POST
def shifts_copy_week(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    start = normalize_start(date.fromisoformat(request.POST["start"]), "week")
    source_dates = week_dates(start - timedelta(days=7))
    source_rows = list(
        ShiftAssignment.objects.filter(
            shift_type__department=department,
            date__gte=source_dates[0],
            date__lte=source_dates[-1],
        ).select_related("shift_type", "times_set_by", "times_set_by__role")
    )
    with transaction.atomic():
        created, skips = _write_planned(plan_copy(source_rows, timedelta(days=7), request.user))
    if created == 0 and not skips:
        notice = _("Nothing to copy.")
    else:
        notice = _("Copied %(count)s shifts.") % {"count": created}
    return _grid_response(request, department, retarget=False, notice=notice, skips=skips)
```

Extend `_grid_response` so its signature is `_grid_response(request, department, retarget=False, notice="", skips=None)` and both values are in the template context.

Print `notice` in `rota.html` as `<p class="notice">{{ notice }}</p>`. Skip lines include the person, the date, and `item["skip"]` (`"archived shift type"`, `"already assigned"`, or `"overlaps"`).

`shifts_repeat_week` uses `_write_planned` inside one `transaction.atomic`. On a bad `weeks` value return the rota page with `error=_("Enter a number of weeks from 1 to 12.")` and do not open a transaction. On success the notice is `_("Repeated %(count)s shifts.")`.

```python
@login_required
@require_POST
def shifts_repeat_week(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    start = normalize_start(date.fromisoformat(request.POST["start"]), "week")
    try:
        weeks = int(request.POST.get("weeks") or "")
    except ValueError:
        weeks = 0
    if weeks < 1 or weeks > REPEAT_WEEKS_MAX:
        return _grid_response(
            request,
            department,
            retarget=False,
            error=_("Enter a number of weeks from 1 to 12."),
        )
    source_rows = list(
        ShiftAssignment.objects.filter(
            shift_type__department=department,
            date__gte=start,
            date__lte=start + timedelta(days=6),
        ).select_related("shift_type", "times_set_by", "times_set_by__role")
    )
    created = 0
    skips = []
    with transaction.atomic():
        for k in range(1, weeks + 1):
            made, skipped = _write_planned(plan_copy(source_rows, timedelta(days=7 * k), request.user))
            created += made
            skips.extend(skipped)
            source_rows = list(
                ShiftAssignment.objects.filter(
                    shift_type__department=department,
                    date__gte=start,
                    date__lte=start + timedelta(days=6),
                ).select_related("shift_type", "times_set_by", "times_set_by__role")
            )
    notice = _("Repeated %(count)s shifts.") % {"count": created}
    return _grid_response(request, department, retarget=False, notice=notice, skips=skips)
```

`_grid_response` accepts `error=""` and `rota.html` prints `{% if error %}<p class="notice notice-error">{{ error }}</p>{% endif %}`.

Add the two buttons only in `rota.html` when `view == "week"`:

```html
<form method="post" action="{% url 'shifts_copy_week' %}">
  {% csrf_token %}
  <input type="hidden" name="department" value="{{ department.pk }}">
  <input type="hidden" name="start" value="{{ start|date:'Y-m-d' }}">
  <button class="btn secondary" type="submit">{% trans "Copy last week" %}</button>
</form>
<form method="post" action="{% url 'shifts_repeat_week' %}">
  {% csrf_token %}
  <input type="hidden" name="department" value="{{ department.pk }}">
  <input type="hidden" name="start" value="{{ start|date:'Y-m-d' }}">
  <input type="number" name="weeks" min="1" max="12" value="1">
  <button class="btn secondary" type="submit">{% trans "Repeat this week forward" %}</button>
</form>
```

Append:

```python
path("rota/copy-week/", views.shifts_copy_week, name="shifts_copy_week"),
path("rota/repeat-week/", views.shifts_repeat_week, name="shifts_repeat_week"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.CopyWeekTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/services.py shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/rota.html
git commit -m "Add copy week and repeat forward"
```

## Task 8: Rotation suggester and auto-fill nights

**Files:**
- Modify: `shifts/services.py`, `shifts/views.py`, `shifts/urls.py`, `templates/shifts/rota.html`, `templates/shifts/calc_rotation.html`, `shifts/tests.py`

**Interfaces:**
- Consumes: `NIGHT_ROTATION_LOOKBACK_DAYS`, `effective_interval`, `neighbor_conflict`.
- Produces: `suggest_nights(people, dates, shift_type, existing_by_user) -> list[dict]`. Each dict is `{"date", "user_id", "back_to_back": bool}` or `{"date", "gap": True}`. `existing_by_user` maps `user_id` to a list of `ShiftAssignment`.

- [ ] **Step 1: Write the failing test**

```python
class RotationTests(TestCase):
    def test_three_people_six_nights_are_even_and_not_consecutive(self):
        from shifts.services import suggest_nights

        department = make_department("Fair")
        people = [make_user(f"fair-{i}", "support", department) for i in range(3)]
        night = make_shift_type(department, name="Fair night")
        dates = [date(2026, 10, 5) + timedelta(days=i) for i in range(6)]
        result = suggest_nights(people, dates, night, {person.pk: [] for person in people})
        assigned = [row for row in result if not row.get("gap")]
        counts = {}
        for row in assigned:
            counts[row["user_id"]] = counts.get(row["user_id"], 0) + 1
        self.assertEqual(sorted(counts.values()), [2, 2, 2])
        by_date = {row["date"]: row["user_id"] for row in assigned}
        for idx in range(1, 6):
            self.assertNotEqual(by_date[dates[idx]], by_date[dates[idx - 1]])

    def test_apply_does_not_overwrite(self):
        department = make_department("Keep")
        role = make_role("Keep lead", can_manage_shifts=True)
        manager = make_user("keep-lead", "support", department, role)
        agent = make_user("keep-agent", "support", department)
        night = make_shift_type(department, name="Keep night")
        existing = make_assignment(agent, night, date(2026, 10, 5))
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_calc_rotation"), {
            "department": department.pk,
            "start": "2026-10-05",
            "end": "2026-10-05",
            "shift_type": night.pk,
            "users": [agent.pk],
            "action": "apply",
        })
        self.assertContains(response, "already assigned")
        existing.refresh_from_db()
        self.assertEqual(existing.shift_type_id, night.pk)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.RotationTests -v 1`

Expected: FAIL with `ImportError` for `suggest_nights`.

- [ ] **Step 3: Write the minimal implementation**

Append to `shifts/services.py`. Lookback `last` is only the latest night-type date in `[start - 14 days, start)`. Do not replace `last` with a date proposed in this run. A night type whose times are 18:00–23:00 still counts. A day type does not.

```python
def suggest_nights(people, dates, shift_type, existing_by_user):
    if not dates:
        return []
    start = dates[0]
    lookback_from = start - timedelta(days=NIGHT_ROTATION_LOOKBACK_DAYS)
    stats = {}
    for person in people:
        rows = existing_by_user.get(person.pk, [])
        nights = [
            row.date for row in rows
            if lookback_from <= row.date < start and row.shift_type.is_night
        ]
        stats[person.pk] = {
            "lookback": len(nights),
            "last": max(nights) if nights else None,
            "proposed": 0,
            "dates": {row.date for row in rows},
            "night_dates": {row.date for row in rows if row.shift_type.is_night},
            "intervals": [effective_interval(row) for row in rows],
        }
    result = []
    for day in dates:
        target = interval_for(day, shift_type.start_time, shift_type.end_time)
        preferred = []
        backup = []
        for person in people:
            st = stats[person.pk]
            if day in st["dates"]:
                continue
            if any(overlaps(target, existing) for existing in st["intervals"]):
                continue
            if (day - timedelta(days=1)) in st["night_dates"]:
                backup.append(person)
            else:
                preferred.append(person)
        pool = preferred or backup
        if not pool:
            result.append({"date": day, "gap": True})
            continue

        def sort_key(person, stats=stats):
            st = stats[person.pk]
            last = st["last"] or date.min
            return (st["lookback"] + st["proposed"], last, person.pk)

        chosen = min(pool, key=sort_key)
        st = stats[chosen.pk]
        st["proposed"] += 1
        st["dates"].add(day)
        st["night_dates"].add(day)
        st["intervals"].append(target)
        result.append({
            "date": day,
            "user_id": chosen.pk,
            "back_to_back": not preferred,
        })
    return result
```

Append these imports if they are not already at the top of `shifts/views.py`:

```python
from django.db import transaction

from shifts.services import interval_for, neighbor_conflict, overlap_message, suggest_nights
```

`timezone` is already imported in the Task 4 header. `get_object_or_404`, `User`, and `ShiftType` are already imported.

```python
def _dates_inclusive(start, end):
    if end < start:
        start, end = end, start
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _people_and_existing(people):
    by_user = {person.pk: [] for person in people}
    rows = ShiftAssignment.objects.filter(user__in=people).select_related("shift_type", "user")
    for row in rows:
        by_user.setdefault(row.user_id, []).append(row)
    return by_user


def _apply_rotation(proposals, shift_type, department):
    created = 0
    skips = []
    with transaction.atomic():
        for item in proposals:
            if item.get("gap"):
                continue
            user = User.objects.filter(pk=item["user_id"]).select_related("role").first()
            if (
                user is None
                or user.user_type != User.UserType.SUPPORT
                or user.status != User.Status.ACTIVE
                or user.department_id != department.pk
            ):
                item["skip"] = _("Only active support users in this department can be assigned.")
                skips.append(item)
                continue
            if shift_type.archived or not shift_type.is_night or shift_type.department_id != department.pk:
                item["skip"] = _("Archived shift types cannot be assigned.")
                skips.append(item)
                continue
            if ShiftAssignment.objects.filter(user_id=user.pk, date=item["date"]).exists():
                item["skip"] = "already assigned"
                skips.append(item)
                continue
            probe = ShiftAssignment(user=user, date=item["date"], shift_type=shift_type)
            start_dt, end_dt = interval_for(item["date"], shift_type.start_time, shift_type.end_time)
            other = neighbor_conflict(probe, start_dt, end_dt)
            if other:
                item["skip"] = overlap_message(other)
                skips.append(item)
                continue
            ShiftAssignment.objects.create(
                user=user,
                shift_type=shift_type,
                date=item["date"],
                start_time_override=None,
                end_time_override=None,
                times_set_by=None,
                times_set_at=None,
                checked_in_at=None,
            )
            created += 1
    return created, skips


@login_required
@require_POST
def shifts_calc_rotation(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    shift_type = get_object_or_404(ShiftType, pk=request.POST.get("shift_type"), department=department)
    start = date.fromisoformat(request.POST.get("start"))
    end = date.fromisoformat(request.POST.get("end"))
    dates = _dates_inclusive(start, end)
    people = list(User.objects.filter(
        pk__in=request.POST.getlist("users"),
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ))
    proposals = suggest_nights(people, dates, shift_type, _people_and_existing(people))
    created = 0
    skips = []
    if request.POST.get("action") == "apply":
        for person in people:
            for day in dates:
                if ShiftAssignment.objects.filter(user=person, date=day).exists():
                    skips.append({"date": day, "user_id": person.pk, "skip": "already assigned"})
        created, applied_skips = _apply_rotation(
            [item for item in proposals if not item.get("gap")],
            shift_type,
            department,
        )
        skips.extend(applied_skips)
    return render(request, "shifts/calc_rotation.html", {
        "proposals": proposals,
        "skips": skips,
        "created": created,
        "department": department,
        "shift_type": shift_type,
    })


@login_required
@require_POST
def shifts_auto_fill(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    _view, _start, dates = _rota_dates(request)
    night_types = list(
        ShiftType.objects.filter(department=department, archived=False, is_night=True).order_by("name")
    )
    if not night_types:
        return _grid_response(request, department, notice=_("This department has no night shift."))
    chosen_id = request.POST.get("shift_type")
    shift_type = night_types[0]
    if chosen_id:
        shift_type = get_object_or_404(
            ShiftType, pk=chosen_id, department=department, archived=False, is_night=True,
        )
    elif len(night_types) > 1:
        return render(request, "shifts/calc_rotation.html", {
            "pick_types": night_types,
            "department": department,
            "proposals": [],
            "skips": [],
            "created": 0,
        })
    people = list(User.objects.filter(
        department=department,
        user_type=User.UserType.SUPPORT,
        status=User.Status.ACTIVE,
    ))
    proposals = suggest_nights(people, dates, shift_type, _people_and_existing(people))
    if request.POST.get("action") != "apply":
        return render(request, "shifts/calc_rotation.html", {
            "proposals": proposals,
            "skips": [],
            "created": 0,
            "department": department,
            "shift_type": shift_type,
            "can_apply": True,
        })
    created, skips = _apply_rotation(proposals, shift_type, department)
    return _grid_response(
        request,
        department,
        notice=_("Filled %(count)s night shifts.") % {"count": created},
        skips=skips,
    )
```

`calc_rotation.html` renders each non-gap proposal as a row. When `back_to_back` is true the row contains `{% trans "Back-to-back" %}`. A gap renders `{% blocktrans trimmed with date=row.date|date:"Y-m-d" %}Nobody available on {{ date }}.{% endblocktrans %}`. Each skip renders `{{ skip.skip }}`, which is how the apply test finds `already assigned`. Preview (`action` other than `apply`) does not call `_apply_rotation` and does not write. Apply never calls `save()` or `update()` on an existing row.

Auto-fill uses the visible rota dates from `_rota_dates` (POST `view` and `start`). People are every active support user in the department. Zero non-archived night types: notice `"This department has no night shift."` and no writes. One night type: preview immediately. Several, and no `shift_type` posted: the response is the picker. The rota toolbar form posts `action=preview` with `{% csrf_token %}`. Apply is a second POST with `action=apply` and the same token.

```html
<form method="post" action="{% url 'shifts_auto_fill' %}">
  {% csrf_token %}
  <input type="hidden" name="department" value="{{ department.pk }}">
  <input type="hidden" name="view" value="{{ view }}">
  <input type="hidden" name="start" value="{{ start|date:'Y-m-d' }}">
  <input type="hidden" name="action" value="preview">
  <button class="btn secondary" type="submit">{% trans "Auto-fill nights" %}</button>
</form>
```

The apply form in `calc_rotation.html`, shown when `can_apply` is true:

```html
<form method="post" action="{% url 'shifts_auto_fill' %}">
  {% csrf_token %}
  <input type="hidden" name="department" value="{{ department.pk }}">
  <input type="hidden" name="view" value="{{ request.POST.view }}">
  <input type="hidden" name="start" value="{{ request.POST.start }}">
  <input type="hidden" name="shift_type" value="{{ shift_type.pk }}">
  <input type="hidden" name="action" value="apply">
  <button class="btn primary" type="submit">{% trans "Apply" %}</button>
</form>
```

Calculator rotation form in `calculator.html`:

```html
<form method="post" action="{% url 'shifts_calc_rotation' %}" hx-post="{% url 'shifts_calc_rotation' %}" hx-target="#shifts-rotation">
  {% csrf_token %}
  <input type="hidden" name="department" value="{{ department.pk }}">
  <label for="rot-start">{% trans "Start" %}</label>
  <input id="rot-start" type="date" name="start">
  <label for="rot-end">{% trans "End" %}</label>
  <input id="rot-end" type="date" name="end">
  <label for="rot-type">{% trans "Shift type" %}</label>
  <select id="rot-type" name="shift_type"></select>
  <label for="rot-users">{% trans "People" %}</label>
  <select id="rot-users" name="users" multiple></select>
  <button class="btn secondary" type="submit" name="action" value="preview">{% trans "Preview" %}</button>
  <button class="btn primary" type="submit" name="action" value="apply">{% trans "Apply" %}</button>
</form>
```

Append:

```python
path("rota/auto-fill/", views.shifts_auto_fill, name="shifts_auto_fill"),
path("calculator/rotation/", views.shifts_calc_rotation, name="shifts_calc_rotation"),
```

Add these methods to `RotationTests` so the spec’s fairness cases are code, not a note:

```python
def test_two_people_two_dates_are_one_each(self):
    from shifts.services import suggest_nights

    department = make_department("Pair")
    people = [make_user(f"pair-{i}", "support", department) for i in range(2)]
    night = make_shift_type(department, name="Pair night")
    dates = [date(2026, 10, 5), date(2026, 10, 6)]
    result = suggest_nights(people, dates, night, {person.pk: [] for person in people})
    self.assertEqual([row["user_id"] for row in result], [people[0].pk, people[1].pk])
    self.assertFalse(any(row["back_to_back"] for row in result))

def test_one_person_second_night_is_back_to_back(self):
    from shifts.services import suggest_nights

    department = make_department("Solo")
    person = make_user("solo", "support", department)
    night = make_shift_type(department, name="Solo night")
    dates = [date(2026, 10, 5), date(2026, 10, 6)]
    result = suggest_nights([person], dates, night, {person.pk: []})
    self.assertEqual(result[1]["back_to_back"], True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.RotationTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/services.py shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/rota.html templates/shifts/calc_rotation.html
git commit -m "Add night rotation preview and auto-fill"
```

## Task 9: Calculator hours, length, and coverage

**Files:**
- Modify: `shifts/views.py`, `shifts/urls.py`, `shifts/tests.py`
- Create: `templates/shifts/calculator.html`, `templates/shifts/calc_hours.html`, `templates/shifts/calc_length.html`, `templates/shifts/calc_coverage.html`

**Interfaces:**
- Consumes: `clipped_day_night_minutes`, `clock_length`, `effective_interval`, `normalize_start`, `week_dates`, `month_dates`.
- Produces: `shifts_calculator`, `shifts_calc_hours`, `shifts_calc_length`, `shifts_calc_coverage`. All manager-only. Coverage ignores `checked_in_at`.

- [ ] **Step 1: Write the failing test**

```python
class CalculatorTests(TestCase):
    def test_length_reports_after_midnight_separately(self):
        department = make_department("Calc")
        manager = make_user("calc-lead", "support", department, make_role("Calc lead", can_manage_shifts=True))
        self.client.force_login(manager)
        response = self.client.get(reverse("shifts_calc_length"), {"start": "22:00", "end": "06:00"})
        self.assertContains(response, "8")
        self.assertContains(response, "6")
        self.assertContains(response, "after midnight")

    def test_support_forbidden(self):
        department = make_department("Calc2")
        agent = make_user("calc-agent", "support", department)
        self.client.force_login(agent)
        self.assertEqual(self.client.get(reverse("shifts_calculator")).status_code, 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.CalculatorTests -v 1`

Expected: FAIL with `NoReverseMatch`.

- [ ] **Step 3: Write the minimal implementation**

```python
def _hours_minutes(minutes):
    return minutes // 60, minutes % 60


@login_required
@require_GET
def shifts_calculator(request):
    if not is_shift_manager(request.user):
        return _forbid()
    return _shell(request, "shifts/calculator.html", {
        "departments": Department.objects.order_by("name"),
    })


@login_required
@require_GET
def shifts_calc_length(request):
    if not is_shift_manager(request.user):
        return _forbid()
    try:
        start_t = time.fromisoformat(request.GET.get("start", ""))
        end_t = time.fromisoformat(request.GET.get("end", ""))
    except ValueError:
        start_t = end_t = None
    if not start_t or not end_t or start_t == end_t:
        return render(request, "shifts/calc_length.html", {"error": _("Start and end must differ.")})
    total, after = clock_length(start_t, end_t)
    hours, minutes = _hours_minutes(total)
    after_hours, after_minutes = _hours_minutes(after)
    return render(request, "shifts/calc_length.html", {
        "total_text": _("%(hours)s hours %(minutes)s minutes") % {"hours": hours, "minutes": minutes},
        "after_text": _("%(hours)s hours %(minutes)s minutes after midnight.") % {
            "hours": after_hours,
            "minutes": after_minutes,
        },
    })
```

Append these imports if they are not already at the top of `shifts/views.py`. `timezone` is already imported.

```python
from shifts.services import aware_on, clipped_day_night_minutes, clock_length, effective_interval
```

```python
def _format_minutes(minutes):
    hours, mins = _hours_minutes(minutes)
    return _("%(hours)s hours %(minutes)s minutes") % {"hours": hours, "minutes": mins}


@login_required
@require_GET
def shifts_calc_hours(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    range_start = aware_on(dates[0], time(0, 0))
    range_end = aware_on(dates[-1] + timedelta(days=1), time(0, 0))
    totals = {}
    for row in bundle["assignments"]:
        day_m, night_m = clipped_day_night_minutes(row, range_start, range_end)
        bucket = totals.setdefault(row.user_id, {"user": row.user, "day": 0, "night": 0})
        bucket["day"] += day_m
        bucket["night"] += night_m
    people = []
    for bucket in totals.values():
        if bucket["day"] == 0 and bucket["night"] == 0:
            continue
        people.append({
            "name": display_name(bucket["user"]),
            "day": _format_minutes(bucket["day"]),
            "night": _format_minutes(bucket["night"]),
            "total": _format_minutes(bucket["day"] + bucket["night"]),
        })
    return render(request, "shifts/calc_hours.html", {
        "people": people,
        "department": department,
        "view": view,
        "start": start,
    })


@login_required
@require_GET
def shifts_calc_coverage(request):
    if not is_shift_manager(request.user):
        return _forbid()
    department = _selected_department(request)
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    intervals = [effective_interval(row) for row in bundle["assignments"]]
    rows = []
    for hour in range(24):
        cells = []
        for day in dates:
            bucket_start = aware_on(day, time(hour, 0))
            bucket_end = bucket_start + timedelta(hours=1)
            count = 0
            for start_dt, end_dt in intervals:
                if start_dt < bucket_end and bucket_start < end_dt:
                    count += 1
            cells.append({"day": day, "hour": hour, "count": count})
        rows.append({"hour": hour, "cells": cells})
    return render(request, "shifts/calc_coverage.html", {
        "rows": rows,
        "dates": dates,
        "department": department,
        "view": view,
        "start": start,
    })
```

`_rota_bundle` already loads the day before the first visible date, so a Friday night covers Saturday 00:00 through 05:00. The overlap test is half-open: `start_dt < bucket_end and bucket_start < end_dt`. A shift that ends at 06:00 overlaps hour 5 and does not overlap hour 6. Neither view reads `checked_in_at`.

`calc_hours.html` prints `{{ person.name }}`, `{{ person.day }}`, `{{ person.night }}`, and `{{ person.total }}`. `calc_coverage.html` is:

```html
{% for row in rows %}
  {% for cell in row.cells %}
  <td id="cov-{{ cell.day|date:'Y-m-d' }}-{{ cell.hour }}"{% if cell.count == 0 %} class="shifts-gap"{% endif %}>{{ cell.count }}</td>
  {% endfor %}
{% endfor %}
```

That renders `id="cov-2026-10-06-5">1` and `id="cov-2026-10-06-6" class="shifts-gap">0`. Hours and coverage GET forms in `calculator.html` include `department`, `view`, and `start`. They are GET forms, so they do not need a CSRF token.

Append:

```python
path("calculator/", views.shifts_calculator, name="shifts_calculator"),
path("calculator/hours/", views.shifts_calc_hours, name="shifts_calc_hours"),
path("calculator/length/", views.shifts_calc_length, name="shifts_calc_length"),
path("calculator/coverage/", views.shifts_calc_coverage, name="shifts_calc_coverage"),
```

`calculator.html` extends the shell and contains four sections. Length is a GET form to `shifts_calc_length`. Hours and coverage forms GET their partials with `department`, `view`, and `start`. Rotation’s form is the Task 8 POST.

Inside `{% if is_manager %}`, after the Shift types tab and before the manager Available now link, insert:

```html
<a class="settings-tab" role="tab" tabindex="0"
   aria-selected="{% if request.resolver_match.url_name == 'shifts_calculator' %}true{% else %}false{% endif %}"
   href="{% url 'shifts_calculator' %}"
   hx-get="{% url 'shifts_calculator' %}"
   hx-target="#shell-content"
   hx-swap="innerHTML show:window:top settle:0"
   hx-push-url="true"
   hx-sync="#shell-content:replace"
   onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); window.htmx.trigger(this, 'click');}">{% trans "Calculator" %}</a>
```

Add to `CalculatorTests`:

```python
def test_quarter_hour_length(self):
    department = make_department("Calc3")
    manager = make_user("calc-lead-3", "support", department, make_role("Calc lead 3", can_manage_shifts=True))
    self.client.force_login(manager)
    response = self.client.get(reverse("shifts_calc_length"), {"start": "09:00", "end": "12:30"})
    self.assertContains(response, "3 hours 30 minutes")
    self.assertContains(response, "0 hours 0 minutes after midnight")

def test_coverage_counts_overnight_until_but_not_including_06(self):
    department = make_department("Heat")
    manager = make_user("heat-lead", "support", department, make_role("Heat lead", can_manage_shifts=True))
    agent = make_user("heat-agent", "support", department)
    night = make_shift_type(department, name="Heat night")
    make_assignment(agent, night, date(2026, 10, 5))  # Monday 22:00–06:00
    self.client.force_login(manager)
    response = self.client.get(reverse("shifts_calc_coverage"), {
        "department": department.pk,
        "view": "week",
        "start": "2026-10-03",
    })
    self.assertContains(response, 'id="cov-2026-10-06-5">1')
    self.assertContains(response, 'id="cov-2026-10-06-6" class="shifts-gap">0')
```

Also append this test. 18:00–23:00 covers hours 18 through 22 only:

```python
def test_same_evening_covers_18_through_22(self):
    department = make_department("Heat eve")
    manager = make_user("heat-lead-2", "support", department, make_role("Heat lead 2", can_manage_shifts=True))
    agent = make_user("heat-eve", "support", department)
    night = make_shift_type(department, name="Heat eve")
    make_assignment(agent, night, date(2026, 10, 6), time(18, 0), time(23, 0))
    self.client.force_login(manager)
    response = self.client.get(reverse("shifts_calc_coverage"), {
        "department": department.pk,
        "view": "week",
        "start": "2026-10-03",
    })
    self.assertContains(response, 'id="cov-2026-10-06-18">1')
    self.assertContains(response, 'id="cov-2026-10-06-22">1')
    self.assertContains(response, 'id="cov-2026-10-06-23" class="shifts-gap">0')

def test_check_in_does_not_change_hours_or_coverage(self):
    department = make_department("Same hours")
    manager = make_user("same-lead", "support", department, make_role("Same lead", can_manage_shifts=True))
    agent = make_user("same-agent", "support", department)
    day = make_shift_type(department, name="Same day", start=time(9, 0), end=time(17, 0))
    row = make_assignment(agent, day, date(2026, 10, 5))
    self.client.force_login(manager)
    params = {"department": department.pk, "view": "week", "start": "2026-10-03"}
    before_hours = self.client.get(reverse("shifts_calc_hours"), params).content
    before_coverage = self.client.get(reverse("shifts_calc_coverage"), params).content
    row.checked_in_at = aware(2026, 10, 5, 9, 0)
    row.save()
    after_hours = self.client.get(reverse("shifts_calc_hours"), params).content
    after_coverage = self.client.get(reverse("shifts_calc_coverage"), params).content
    self.assertEqual(before_hours, after_hours)
    self.assertEqual(before_coverage, after_coverage)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.CalculatorTests shifts.tests.WeekAndHoursTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/calculator.html templates/shifts/calc_hours.html templates/shifts/calc_length.html templates/shifts/calc_coverage.html templates/shifts/shell.html
git commit -m "Add shift hours, length, and coverage calculators"
```

## Task 10: My shifts and worker night hours

**Files:**
- Modify: `shifts/views.py`, `shifts/urls.py`, `shifts/tests.py`
- Create: `templates/shifts/mine.html`, `templates/shifts/mine_row.html`

**Interfaces:**
- Consumes: `WORKER_HOURS_LOOKBACK_DAYS`, `WORKER_HOURS_MAX_MINUTES`, `interval_for`, `neighbor_conflict`, `overlap_message`.
- Produces: `shifts_mine_hours(request, pk)` POST fields `start_time`, `end_time`, `action` (`save` or `reset`).

- [ ] **Step 1: Write the failing test**

```python
class WorkerHoursTests(TestCase):
    def setUp(self):
        self.department = make_department("Mine")
        self.agent = make_user("mine-agent", "support", self.department)
        self.other = make_user("mine-other", "support", self.department)
        self.night = make_shift_type(self.department, name="Mine night")
        self.day = make_shift_type(self.department, name="Mine day", start=time(9, 0), end=time(17, 0))
        self.today = timezone.localdate()
        self.own = make_assignment(self.agent, self.night, self.today)
        self.client.force_login(self.agent)

    def test_owner_can_set_same_evening_hours(self):
        response = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00",
            "end_time": "23:00",
            "action": "save",
        })
        self.assertEqual(response.status_code, 200)
        self.own.refresh_from_db()
        self.assertEqual(self.own.start_time_override, time(18, 0))
        self.assertEqual(self.own.times_set_by_id, self.agent.pk)

    def test_other_user_and_day_shift_are_403(self):
        foreign = make_assignment(self.other, self.night, self.today)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[foreign.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        }).status_code, 403)
        foreign.refresh_from_db()
        self.assertIsNone(foreign.start_time_override)
        day_row = make_assignment(self.agent, self.day, self.today + timedelta(days=1))
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[day_row.pk]), {
            "start_time": "10:00", "end_time": "15:00", "action": "save",
        }).status_code, 403)

    def test_eight_days_ago_rejected_and_seven_accepted(self):
        old = make_assignment(self.agent, self.night, self.today - timedelta(days=8))
        response = self.client.post(reverse("shifts_mine_hours", args=[old.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        })
        self.assertContains(response, "last 7 days")
        old.refresh_from_db()
        self.assertIsNone(old.start_time_override)
        recent = make_assignment(self.agent, self.night, self.today - timedelta(days=7))
        ok = self.client.post(reverse("shifts_mine_hours", args=[recent.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        })
        self.assertEqual(ok.status_code, 200)
        recent.refresh_from_db()
        self.assertEqual(recent.start_time_override, time(18, 0))

    def test_branch_post_forbidden(self):
        branch = make_user("mine-branch", "branch")
        self.client.force_login(branch)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        }).status_code, 403)

    def test_length_cap_equal_times_overlap_and_reset(self):
        too_long = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "00:00", "end_time": "16:30", "action": "save",
        })
        self.assertContains(too_long, "16 hours")
        self.own.refresh_from_db()
        self.assertIsNone(self.own.start_time_override)
        equal = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "18:00", "action": "save",
        })
        self.assertContains(equal, "16 hours")
        crossing = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "02:00", "action": "save",
        })
        self.assertEqual(crossing.status_code, 200)
        self.own.refresh_from_db()
        self.assertEqual(self.own.end_time_override, time(2, 0))
        self.own.start_time_override = None
        self.own.end_time_override = None
        self.own.times_set_by = None
        self.own.times_set_at = None
        self.own.save()
        neighbor = make_assignment(self.agent, self.night, self.today + timedelta(days=1), time(1, 0), time(9, 0))
        blocked = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "02:00", "action": "save",
        })
        self.assertContains(blocked, "overlaps")
        self.own.refresh_from_db()
        self.assertIsNone(self.own.start_time_override)
        neighbor.delete()
        self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        })
        reset = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {"action": "reset"})
        self.assertEqual(reset.status_code, 200)
        self.own.refresh_from_db()
        self.assertIsNone(self.own.start_time_override)
        self.assertIsNone(self.own.times_set_by_id)
        self.assertIsNone(self.own.times_set_at)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.WorkerHoursTests -v 1`

Expected: FAIL with `NoReverseMatch: 'shifts_mine_hours'`.

- [ ] **Step 3: Write the minimal implementation**

```python
from shifts.services import (
    WORKER_HOURS_LOOKBACK_DAYS,
    WORKER_HOURS_MAX_MINUTES,
    clock_length,
    interval_for,
    neighbor_conflict,
    overlap_message,
)


@login_required
@require_POST
def shifts_mine_hours(request, pk):
    assignment = get_object_or_404(
        ShiftAssignment.objects.select_related("shift_type", "user"),
        pk=pk,
    )
    if assignment.user_id != request.user.id:
        return _forbid()
    if not assignment.shift_type.is_night:
        return _forbid()
    if request.user.user_type != "support" and not is_shift_manager(request.user):
        return _forbid()
    today = timezone.localdate()
    if assignment.date < today - timedelta(days=WORKER_HOURS_LOOKBACK_DAYS):
        return _mine_row(request, assignment, _("You can only change hours from the last 7 days onward."))
    if request.POST.get("action") == "reset":
        assignment.start_time_override = None
        assignment.end_time_override = None
        assignment.times_set_by = None
        assignment.times_set_at = None
        assignment.save()
        return _mine_row(request, assignment, "")
    start_raw = request.POST.get("start_time") or ""
    end_raw = request.POST.get("end_time") or ""
    if not start_raw or not end_raw:
        return _mine_row(request, assignment, _("Enter both a start and an end time."))
    start_t = time.fromisoformat(start_raw)
    end_t = time.fromisoformat(end_raw)
    total, _after = clock_length(start_t, end_t)
    if total <= 0 or total > WORKER_HOURS_MAX_MINUTES:
        return _mine_row(request, assignment, _("This shift must be longer than 0 hours and no more than 16 hours."))
    try:
        start_dt, end_dt = interval_for(assignment.date, start_t, end_t)
    except ValueError as exc:
        return _mine_row(request, assignment, str(exc))
    other = neighbor_conflict(assignment, start_dt, end_dt, exclude_pk=assignment.pk)
    if other:
        return _mine_row(request, assignment, overlap_message(other))
    assignment.start_time_override = start_t
    assignment.end_time_override = end_t
    assignment.times_set_by = request.user
    assignment.times_set_at = timezone.now()
    assignment.save()
    return _mine_row(request, assignment, "")


def _mine_row(request, assignment, error):
    return render(request, "shifts/mine_row.html", {"assignment": assignment, "error": error})
```

Ignore posted `user`, `date`, and `shift_type`. The 7-day window and the 16-hour cap apply even when the caller is a manager editing their own row. A 403 body is `_forbid()` only. It does not render the other assignment.

`mine.html` lists the caller’s assignments with `date >= today`, plus that user’s night rows with `date >= today - 7 days` and `date < today`. Empty set: `{% trans "You have no upcoming shifts." %}`. When an effective interval contains `timezone.now()`, show `"You are on shift until %(end)s."` with the effective end in `H:i`. Night rows include `mine_row.html` with `id="shift-mine-{{ assignment.pk }}"` and:

```html
<form method="post" action="{% url 'shifts_mine_hours' assignment.pk %}"
      hx-post="{% url 'shifts_mine_hours' assignment.pk %}"
      hx-target="#shift-mine-{{ assignment.pk }}"
      hx-swap="outerHTML">
  {% csrf_token %}
  <p>{% trans "Set my hours" %}</p>
  <label for="mine-start-{{ assignment.pk }}">{% trans "Start time" %}</label>
  <input id="mine-start-{{ assignment.pk }}" type="time" name="start_time" value="{{ assignment.start_time_override|default:assignment.shift_type.start_time|time:'H:i' }}">
  <label for="mine-end-{{ assignment.pk }}">{% trans "End time" %}</label>
  <input id="mine-end-{{ assignment.pk }}" type="time" name="end_time" value="{{ assignment.end_time_override|default:assignment.shift_type.end_time|time:'H:i' }}">
  {% if error %}<p class="notice notice-error">{{ error }}</p>{% endif %}
  <button class="btn primary" type="submit" name="action" value="save">{% trans "Save" %}</button>
  <button class="btn secondary" type="submit" name="action" value="reset">{% trans "Reset to shift default" %}</button>
</form>
```

The row id is `shift-mine-{{ assignment.pk }}` on the `<tr>`. Day rows have no form. The POST response is that row partial. Save and Reset are the two submit buttons in the form above. Both ride the same `{% csrf_token %}`.

Append:

```python
path("mine/<int:pk>/hours/", views.shifts_mine_hours, name="shifts_mine_hours"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.WorkerHoursTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/mine.html templates/shifts/mine_row.html
git commit -m "Let support staff record night shift hours"
```

## Task 11: Day-shift check-in and manager clear

**Files:**
- Modify: `shifts/views.py`, `shifts/urls.py`, `templates/shifts/check_in_panel.html`, `templates/shifts/mine.html`, `templates/shifts/rota.html`, `templates/shifts/rota_grid.html`, `templates/shifts/cell_form.html`, `shifts/tests.py`

**Interfaces:**
- Consumes: `check_in_state`, `CHECK_IN_EARLY_MINUTES`, `effective_interval`.
- Produces: `shifts_check_in(request, pk)` POST with no time field. Cell POST `clear_check_in=1` sets `checked_in_at` to null. `check_in_marker(assignment, now) -> str` returns `""`, `"checked"`, `"not"`, or `"missed"`.

- [ ] **Step 1: Write the failing test**

```python
class CheckInTests(TestCase):
    def setUp(self):
        self.department = make_department("Check")
        self.agent = make_user("check-agent", "support", self.department)
        self.other = make_user("check-other", "support", self.department)
        self.day = make_shift_type(self.department, name="Check day", start=time(9, 0), end=time(17, 0))
        self.night = make_shift_type(self.department, name="Check night")
        self.today = date(2026, 6, 2)
        self.row = make_assignment(self.agent, self.day, self.today)
        self.client.force_login(self.agent)

    def _at(self, hh, mm=0):
        return _both_clocks(aware(2026, 6, 2, hh, mm), date(2026, 6, 2))

    def test_window_and_idempotent_press(self):
        with self._at(8, 0):
            too_soon = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.assertContains(too_soon, "30 minutes")
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)
        with self._at(8, 40):
            first = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.row.refresh_from_db()
        stamped = self.row.checked_in_at
        self.assertIsNotNone(stamped)
        with self._at(9, 0):
            second = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.row.refresh_from_db()
        self.assertEqual(self.row.checked_in_at, stamped)
        self.assertContains(second, "Checked in at")

    def test_hidden_for_night_other_and_branch(self):
        night = make_assignment(self.agent, self.night, self.today + timedelta(days=1))
        with self._at(8, 40):
            self.assertEqual(self.client.post(reverse("shifts_check_in", args=[night.pk])).status_code, 403)
        foreign = make_assignment(self.other, self.day, self.today + timedelta(days=2))
        self.assertEqual(self.client.post(reverse("shifts_check_in", args=[foreign.pk])).status_code, 403)
        self.client.force_login(make_user("check-branch", "branch"))
        self.assertEqual(self.client.post(reverse("shifts_check_in", args=[self.row.pk])).status_code, 403)

    def test_manager_clear_worker_cannot(self):
        self.row.checked_in_at = aware(2026, 6, 2, 8, 40)
        self.row.save()
        self.assertEqual(self.client.post(reverse("shifts_cell"), {
            "clear_check_in": "1",
            "user": self.agent.pk,
            "date": "2026-06-02",
            "department": self.department.pk,
            "shift_type": self.day.pk,
        }).status_code, 403)
        manager = make_user("check-lead", "support", self.department, make_role("Check lead", can_manage_shifts=True))
        self.client.force_login(manager)
        self.client.post(reverse("shifts_cell"), {
            "clear_check_in": "1",
            "user": self.agent.pk,
            "date": "2026-06-02",
            "department": self.department.pk,
            "shift_type": self.day.pk,
        })
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)
```

Above the test class, add this helper so `with self._at(...)` patches both clocks. `ExitStack` is not required.

```python
from contextlib import contextmanager

@contextmanager
def _both_clocks(now, day):
    with patch("django.utils.timezone.now", return_value=now), \
         patch("django.utils.timezone.localdate", return_value=day):
        yield
```

The window test’s 08:00 POST is too early, 08:40 is inside the window, and the second POST at 09:00 keeps the first timestamp.

Also append:

```python
def test_panel_only_for_the_owning_support_user(self):
    with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 8, 40)), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        mine = self.client.get(reverse("shifts_mine"))
    self.assertContains(mine, 'id="shifts-check-in"')
    self.client.force_login(self.other)
    with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 8, 40)), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        other = self.client.get(reverse("shifts_mine"))
    self.assertNotContains(other, 'id="shifts-check-in"')
    manager = make_user("check-panel-lead", "support", self.department, make_role("Panel lead", can_manage_shifts=True))
    make_assignment(manager, self.day, self.today)
    self.client.force_login(manager)
    with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 8, 40)), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        rota = self.client.get(reverse("shifts_rota"))
    self.assertContains(rota, 'id="shifts-check-in"')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.CheckInTests -v 1`

Expected: FAIL with `NoReverseMatch: 'shifts_check_in'`.

- [ ] **Step 3: Write the minimal implementation**

```python
@login_required
@require_POST
def shifts_check_in(request, pk):
    assignment = get_object_or_404(
        ShiftAssignment.objects.select_related("shift_type", "user"),
        pk=pk,
    )
    if assignment.user_id != request.user.id:
        return _forbid()
    if request.user.user_type != "support":
        return _forbid()
    if assignment.shift_type.is_night:
        return _forbid()
    if assignment.date != timezone.localdate():
        return _forbid()
    now = timezone.now()
    if assignment.checked_in_at:
        return render(request, "shifts/check_in_panel.html", {"assignment": assignment, "state": "checked"})
    state = check_in_state(assignment, now)
    if state == "early":
        return render(request, "shifts/check_in_panel.html", {
            "assignment": assignment,
            "state": "early",
            "hint": _("You can check in from 30 minutes before this shift starts."),
        })
    if state == "closed":
        return render(request, "shifts/check_in_panel.html", {
            "assignment": assignment,
            "state": "closed",
            "hint": _("This shift has ended."),
        })
    assignment.checked_in_at = now
    assignment.save(update_fields=["checked_in_at", "updated_at"])
    return render(request, "shifts/check_in_panel.html", {"assignment": assignment, "state": "checked"})
```

Ignore any posted timestamp or `clear_check_in` on this URL. A second press returns the stored timestamp and does not call `save()` again.

In `shifts_cell`, before the empty-`shift_type` delete branch, handle clear:

```python
if request.method == "POST" and request.POST.get("clear_check_in") == "1":
    if existing and not existing.shift_type.is_night:
        existing.checked_in_at = None
        existing.save(update_fields=["checked_in_at", "updated_at"])
    response = _grid_response(request, department, retarget=True)
    response["HX-Trigger"] = "closeModal"
    return response
```

The `shifts_cell` save tail from Task 6 already clears check-in on a day-to-night type change, and only then. Do not add a second `row.save()`. Changing times does not clear `checked_in_at`. The tail is:

```python
    row = existing or ShiftAssignment(user=user, date=on)
    was_day = bool(existing and not existing.shift_type.is_night)
    row.shift_type = shift_type
    if start_t and end_t:
        row.start_time_override = start_t
        row.end_time_override = end_t
        row.times_set_by = request.user
        row.times_set_at = timezone.now()
    if was_day and shift_type.is_night:
        row.checked_in_at = None
    row.save()
```

Add this test to `CheckInTests`:

```python
def test_day_to_night_clears_check_in(self):
    self.row.checked_in_at = aware(2026, 6, 2, 9, 0)
    self.row.save()
    manager = make_user("type-lead", "support", self.department, make_role("Type lead", can_manage_shifts=True))
    self.client.force_login(manager)
    self.client.post(reverse("shifts_cell"), {
        "user": self.agent.pk,
        "date": "2026-06-02",
        "department": self.department.pk,
        "shift_type": self.night.pk,
    })
    self.row.refresh_from_db()
    self.assertEqual(self.row.shift_type_id, self.night.pk)
    self.assertIsNone(self.row.checked_in_at)
```

```python
def check_in_marker(assignment, now) -> str:
    if assignment.shift_type.is_night:
        return ""
    today = timezone.localdate()
    if assignment.date > today:
        return ""
    if assignment.checked_in_at and assignment.date <= today:
        return "checked"
    if assignment.date < today:
        return "missed"
    start_dt, _end = effective_interval(assignment)
    if now >= start_dt:
        return "not"
    return ""
```

Put `check_in_marker` in `shifts/services.py`. The grid template maps `"checked"` to `{% blocktrans trimmed %}Checked in at {{ time }}{% endblocktrans %}` with `H:i`, `"not"` to `{% trans "Not checked in" %}`, and `"missed"` to `{% trans "Missed" %}`. `""` renders nothing.

`check_in_panel.html` id `shifts-check-in`. Include it at the top of `mine.html` when `user.user_type == "support"` and today’s assignment is a day type. Include it at the top of `rota.html` only when `request.user.user_type == "support"` and that user owns today’s day shift. Do not include it on calculator, types, team, or available. Button class `btn primary`, label `{% trans "Check in" %}`. Add `disabled` when `state != "open"`. After success the button is gone and the text is `{% blocktrans trimmed %}Checked in at {{ time }}{% endblocktrans %}`. The cell modal shows a “Clear check-in” submit (`name="clear_check_in" value="1"`) only for managers on a day row with `checked_in_at` set. That POST does not delete the row. Team rota does not render that button.

Form:

```html
<form method="post" action="{% url 'shifts_check_in' assignment.pk %}"
      hx-post="{% url 'shifts_check_in' assignment.pk %}"
      hx-target="#shifts-check-in" hx-swap="outerHTML">
  {% csrf_token %}
</form>
```

Append:

```python
path("mine/<int:pk>/check-in/", views.shifts_check_in, name="shifts_check_in"),
```

`save(update_fields=["checked_in_at", "updated_at"])` still runs `ShiftAssignment.save`, which does not touch `is_night`. `TimeStampedModel.updated_at` is `auto_now`, so include it in `update_fields` or the ETag will miss the write. If `auto_now` ignores a stale in-memory value, call `save()` with no `update_fields` instead. Do not add `check_in_cleared_by`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.CheckInTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/check_in_panel.html templates/shifts/mine.html templates/shifts/rota.html templates/shifts/rota_grid.html templates/shifts/cell_form.html
git commit -m "Add day shift check-in"
```

## Task 12: Team rota

**Files:**
- Modify: `shifts/views.py`, `shifts/urls.py`, `templates/shifts/shell.html`, `shifts/tests.py`
- Create: `templates/shifts/team.html`

**Interfaces:**
- Consumes: the rota grid context builder from Task 6 with `readonly=True`.
- Produces: `shifts_team`. Non-managers are pinned to `request.user.department_id`. A `department` query that differs returns 403.

- [ ] **Step 1: Write the failing test**

```python
class TeamRotaTests(TestCase):
    def test_support_cannot_switch_department(self):
        home = make_department("Home team")
        other = make_department("Other team")
        agent = make_user("team-agent", "support", home)
        self.client.force_login(agent)
        response = self.client.get(reverse("shifts_team"), {"department": other.pk, "start": "2026-10-03"})
        self.assertEqual(response.status_code, 403)

    def test_branch_forbidden(self):
        self.client.force_login(make_user("team-branch", "branch"))
        self.assertEqual(self.client.get(reverse("shifts_team")).status_code, 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.TeamRotaTests -v 1`

Expected: FAIL with `NoReverseMatch: 'shifts_team'`.

- [ ] **Step 3: Write the minimal implementation**

```python
@login_required
@require_GET
def shifts_team(request):
    if request.user.user_type != "support" and not is_shift_manager(request.user):
        return _forbid()
    if is_shift_manager(request.user):
        department = _selected_department(request)
    else:
        requested = request.GET.get("department")
        if requested and str(request.user.department_id) != str(requested):
            return _forbid()
        if not request.user.department_id:
            return _shell(request, "shifts/team.html", {
                "error": _("You are not assigned to a department."),
                "readonly": True,
            })
        department = request.user.department
    view, start, dates = _rota_dates(request)
    bundle = _rota_bundle(department, dates)
    return _shell(request, "shifts/team.html", {
        **bundle,
        "department": department,
        "view": view,
        "start": start,
        "readonly": True,
    })
```

`team.html` extends the shell and includes `rota_grid.html`. `readonly` hides copy, repeat, auto-fill, cell buttons, and “Clear check-in”. Keep the “Set by worker” badge and `check_in_marker`. No check-in panel on this page.

Append:

```python
path("team/", views.shifts_team, name="shifts_team"),
```

In `shell.html`, insert Team rota at the Task 12 comment, after My shifts and still inside `{% if user.user_type == "support" or is_manager %}`, before `{% if not is_manager %}`. Use this anchor:

```html
{% if user.user_type == "support" or is_manager %}
<a class="settings-tab" role="tab" tabindex="0"
   aria-selected="{% if request.resolver_match.url_name == 'shifts_team' %}true{% else %}false{% endif %}"
   href="{% url 'shifts_team' %}"
   hx-get="{% url 'shifts_team' %}"
   hx-target="#shell-content"
   hx-swap="innerHTML show:window:top settle:0"
   hx-push-url="true"
   hx-sync="#shell-content:replace"
   onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); window.htmx.trigger(this, 'click');}">{% trans "Team rota" %}</a>
{% endif %}
```

That insertion leaves the order from Task 4:

- Manager: Rota, Shift types, Calculator, Available now, My shifts, Team rota.
- Support, not manager: My shifts, Team rota, Available now.
- Branch, not manager: Available now only.

The manager Available now link stays inside `{% if is_manager %}`. The other Available now link stays inside `{% if not is_manager %}`. Do not add a third one.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.TeamRotaTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/team.html templates/shifts/shell.html
git commit -m "Add read-only team rota"
```

## Task 13: Available now board, poll, ETag, session defer

**Files:**
- Modify: `shifts/views.py`, `shifts/urls.py`, `templates/shifts/available.html`, `templates/shifts/available_board.html`, `shifts/tests.py`

**Interfaces:**
- Consumes: `effective_interval`, `etag_digest`, `htmx_revalidation_match`, `htmx_not_modified`, `apply_read_etag`.
- Produces: `shifts_available_board`. On 304 only, set `request.ticket_list_304_defer_session_save = True`. Do not edit `core/session_middleware.py`.

- [ ] **Step 1: Write the failing test**

```python
class AvailableNowTests(TestCase):
    def test_night_shift_shows_without_check_in_until_end(self):
        department = make_department("Now")
        agent = make_user("now-agent", "support", department)
        night = make_shift_type(department, name="Now night")
        make_assignment(agent, night, date(2026, 6, 1))
        self.client.force_login(make_user("now-branch", "branch"))
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            shown = self.client.get(reverse("shifts_available_board"))
        self.assertContains(shown, "now-agent")
        self.assertNotContains(shown, "Now night")
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 6, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            hidden = self.client.get(reverse("shifts_available_board"))
        self.assertNotContains(hidden, "now-agent")

    def test_day_shift_needs_check_in_and_etag_changes(self):
        department = make_department("Now day")
        agent = make_user("day-agent", "support", department)
        day = make_shift_type(department, name="Now day", start=time(9, 0), end=time(17, 0))
        row = make_assignment(agent, day, date(2026, 6, 2))
        self.client.force_login(agent)
        noon = aware(2026, 6, 2, 12, 0)
        with patch("django.utils.timezone.now", return_value=noon), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            before = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
        self.assertNotContains(before, "day-agent")
        etag_before = before["ETag"]
        row.checked_in_at = noon
        row.save()
        with patch("django.utils.timezone.now", return_value=noon), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            after = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
        self.assertContains(after, "day-agent")
        self.assertNotEqual(after["ETag"], etag_before)
        with patch("django.utils.timezone.now", return_value=noon), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            cached = self.client.get(
                reverse("shifts_available_board"),
                HTTP_HX_REQUEST="true",
                HTTP_IF_NONE_MATCH=after["ETag"],
            )
        self.assertEqual(cached.status_code, 304)
```

Append these methods to `AvailableNowTests`:

```python
def test_early_check_in_stays_hidden_until_start_and_changes_etag(self):
    department = make_department("Early")
    agent = make_user("early-agent", "support", department)
    day = make_shift_type(department, name="Early day", start=time(9, 0), end=time(17, 0))
    row = make_assignment(agent, day, date(2026, 6, 2))
    self.client.force_login(agent)
    early = aware(2026, 6, 2, 8, 40)
    with patch("django.utils.timezone.now", return_value=early), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        before = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
    row.checked_in_at = early
    row.save()
    with patch("django.utils.timezone.now", return_value=early), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        during = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
    self.assertNotContains(during, "early-agent")
    self.assertNotEqual(during["ETag"], before["ETag"])
    with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 9, 0)), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        started = self.client.get(reverse("shifts_available_board"))
    self.assertContains(started, "early-agent")
    with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 17, 0)), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        ended = self.client.get(reverse("shifts_available_board"))
    self.assertNotContains(ended, "early-agent")

def test_empty_department_and_no_type_name_for_branch(self):
    empty = make_department("Empty desk")
    staffed = make_department("Staffed")
    agent = make_user("staffed-agent", "support", staffed, first_name="", last_name="")
    night = make_shift_type(staffed, name="Secret type")
    make_assignment(agent, night, date(2026, 6, 1))
    self.client.force_login(make_user("board-branch", "branch"))
    with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        response = self.client.get(reverse("shifts_available_board"))
    self.assertContains(response, "Nobody on shift now")
    self.assertContains(response, "staffed-agent")
    self.assertNotContains(response, "Secret type")
    self.assertContains(response, "06:00")

def test_history_restore_is_not_304(self):
    department = make_department("Hist")
    self.client.force_login(make_user("hist-branch", "branch"))
    with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
        first = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
        restored = self.client.get(
            reverse("shifts_available_board"),
            HTTP_HX_REQUEST="true",
            HTTP_IF_NONE_MATCH=first["ETag"],
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
        )
    self.assertEqual(restored.status_code, 200)
```

`make_user` already accepts `first_name` and `last_name`. The empty names in `test_empty_department_and_no_type_name_for_branch` make the board show `staffed-agent`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test shifts.tests.AvailableNowTests -v 1`

Expected: FAIL. The Task 4 page has no board partial and no ETag.

- [ ] **Step 3: Write the minimal implementation**

```python
@login_required
@require_GET
def shifts_available(request):
    return _shell(request, "shifts/available.html", {"board_etag": ""})


@login_required
@require_GET
def shifts_available_board(request):
    now = timezone.now()
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    rows = list(
        ShiftAssignment.objects.filter(date__in=[yesterday, today])
        .select_related("user", "shift_type", "shift_type__department")
    )
    checked = [row.checked_in_at for row in rows if row.checked_in_at]
    on_shift = []
    for row in rows:
        start_dt, end_dt = effective_interval(row)
        if not (start_dt <= now < end_dt):
            continue
        if row.shift_type.is_night or row.checked_in_at:
            on_shift.append((row, end_dt))
    parts = [
        get_language(),
        max(checked).isoformat() if checked else "",
        len(checked),
    ]
    by_department = {}
    for row, end_dt in on_shift:
        by_department.setdefault(row.shift_type.department_id, []).append((row, end_dt))
    for department_id in sorted(by_department):
        tuples = []
        for row, end_dt in by_department[department_id]:
            start_dt, real_end = effective_interval(row)
            tuples.append((
                row.user_id,
                start_dt.isoformat(),
                real_end.isoformat(),
                row.times_set_at.isoformat() if row.times_set_at else "",
                row.checked_in_at.isoformat() if row.checked_in_at else "",
            ))
        parts.append((department_id, tuple(sorted(tuples))))
    etag = etag_digest(parts)
    if htmx_revalidation_match(request, etag):
        request.ticket_list_304_defer_session_save = True
        return htmx_not_modified(etag)
    cards = []
    for department in Department.objects.order_by("name"):
        people = []
        for row, end_dt in sorted(by_department.get(department.pk, []), key=lambda item: item[0].user_id):
            people.append({"name": display_name(row.user), "end": end_dt})
        cards.append({"department": department, "people": people})
    response = render(request, "shifts/available_board.html", {"cards": cards, "board_etag": etag})
    return apply_read_etag(response, etag, request)
```

Do not set the session-defer flag on the 200 path. `available.html` `{% include "shifts/available_board.html" %}`. The end filter prints `{{ person.end|date:"H:i" }}`. Empty `people` renders `{% trans "Nobody on shift now" %}`. Do not render start, type name, colour, phone, or check-in status. A day row is kept only when `checked_in_at` is set and the interval contains now. The `if row.shift_type.is_night or row.checked_in_at` line does that, because a day row with a null check-in fails the `or`.

Query budget, append to `AvailableNowTests`. Create six assignments first. The count must stay at or below 8, which includes the test client’s session and user queries:

```python
def test_board_query_budget(self):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    department = make_department("Budget board")
    night = make_shift_type(department, name="Budget night")
    for index in range(6):
        person = make_user(f"board-{index}", "support", department)
        make_assignment(person, night, date(2026, 6, 1))
    self.client.force_login(make_user("budget-branch", "branch"))
    with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
         patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)), \
         CaptureQueriesContext(connection) as captured:
        self.client.get(reverse("shifts_available_board"))
    self.assertLessEqual(len(captured), 8)
```

Append:

```python
path("available/board/", views.shifts_available_board, name="shifts_available_board"),
```

`shifts_available` from Task 4 stays the page. This task replaces its body so the page includes the board.

`available_board.html`:

```html
<div id="shifts-available-now"
     hx-get="{% url 'shifts_available_board' %}"
     hx-trigger="every 20s [!document.hidden], refresh"
     hx-swap="outerHTML"
     data-no-progress
     data-etag="{{ board_etag }}"
     aria-live="polite">
```

ETag digest: language, max `checked_in_at` isoformat or `""`, count of non-null `checked_in_at` on yesterday and today, then per department the sorted `(user_id, effective_start, effective_end, times_set_at or "", checked_in_at or "")` for rows that passed the filter. On 304:

```python
request.ticket_list_304_defer_session_save = True
return htmx_not_modified(etag)
```

Ignore extra query params. `available.html` includes the board.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test shifts.tests.AvailableNowTests -v 1`

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add shifts/views.py shifts/urls.py shifts/tests.py templates/shifts/available.html templates/shifts/available_board.html
git commit -m "Add available-now board with ETag polling"
```

## Task 14: Arabic catalog and doc rows

**Files:**
- Modify: `shifts/tests.py`, `locale/ar/LC_MESSAGES/django.po`, `locale/ar/LC_MESSAGES/django.mo`, `docs/reference/permissions-matrix.md`, `PROJECT_STANDARDS.md`
- Modify only if a permission test fails: the view in `shifts/views.py` that returned the wrong status

**Interfaces:**
- Consumes: every `{% trans %}`, `{% blocktrans trimmed %}`, and `_()` / `gettext_lazy` string added in earlier tasks.
- Produces: a Shifts section in the permissions matrix and one package-table row in `PROJECT_STANDARDS.md`.

- [ ] **Step 1: Write the failing permission test, then the catalog check**

Append `PermissionMatrixTests`. It covers every name in the spec URL table. Anonymous requests are 302 to `/accounts/login/`. A branch non-manager gets 200 only on `shifts_home` (redirect), `shifts_available`, and `shifts_available_board`. Support non-manager also gets 200 on `shifts_mine`, `shifts_team`, their own `shifts_mine_hours`, and their own `shifts_check_in`. Manager and superuser get 200 on the manager GETs and on preview POSTs. Support and branch POSTs to manager actions are 403. A 403 body does not contain `2099-01-01`.

```python
class PermissionMatrixTests(TestCase):
    def setUp(self):
        self.department = make_department("Perm")
        self.other = make_department("Perm other")
        self.support = make_user("perm-agent", "support", self.department)
        self.outsider = make_user("perm-out", "support", self.other)
        self.branch = make_user("perm-branch", "branch")
        self.manager = make_user("perm-lead", "support", self.department, make_role("Perm lead", can_manage_shifts=True))
        self.superuser = make_user("perm-root", "support", self.department, superuser=True)
        self.night = make_shift_type(self.department, name="Perm night")
        self.day = make_shift_type(self.department, name="Perm day", start=time(0, 0), end=time(23, 59))
        self.row = make_assignment(self.support, self.night, date(2026, 1, 10))
        self.today_row = make_assignment(self.support, self.day, timezone.localdate())

    def _assert_login(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_anonymous_redirects_every_named_url(self):
        gets = [
            reverse("shifts_home"),
            reverse("shifts_rota"),
            reverse("shifts_rota_grid"),
            reverse("shifts_cell"),
            reverse("shifts_types"),
            reverse("shifts_type_add"),
            reverse("shifts_type_edit", args=[self.night.pk]),
            reverse("shifts_calculator"),
            reverse("shifts_calc_hours"),
            reverse("shifts_calc_length"),
            reverse("shifts_calc_coverage"),
            reverse("shifts_available"),
            reverse("shifts_available_board"),
            reverse("shifts_mine"),
            reverse("shifts_team"),
        ]
        for url in gets:
            self._assert_login(self.client.get(url))
        posts = [
            reverse("shifts_cell"),
            reverse("shifts_copy_week"),
            reverse("shifts_repeat_week"),
            reverse("shifts_auto_fill"),
            reverse("shifts_type_archive", args=[self.night.pk]),
            reverse("shifts_calc_rotation"),
            reverse("shifts_mine_hours", args=[self.row.pk]),
            reverse("shifts_check_in", args=[self.today_row.pk]),
        ]
        for url in posts:
            self._assert_login(self.client.post(url, {}))

    def test_branch_support_and_manager_statuses(self):
        manager_gets = [
            "shifts_rota", "shifts_rota_grid", "shifts_types", "shifts_type_add",
            "shifts_calculator", "shifts_calc_hours", "shifts_calc_length", "shifts_calc_coverage",
        ]
        shared_gets = ["shifts_available", "shifts_available_board"]
        support_gets = ["shifts_mine", "shifts_team"]
        for user, forbidden in (
            (self.branch, manager_gets + support_gets),
            (self.support, manager_gets),
        ):
            self.client.force_login(user)
            home = self.client.get(reverse("shifts_home"))
            self.assertEqual(home.status_code, 302, user.username)
            for name in shared_gets:
                self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
            for name in forbidden:
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 403, f"{user.username} {name}")
                self.assertNotContains(response, "2099-01-01", status_code=403)
        self.client.force_login(self.support)
        self.assertEqual(self.client.get(reverse("shifts_mine")).status_code, 200)
        self.assertEqual(self.client.get(reverse("shifts_team")).status_code, 200)
        self.assertEqual(self.client.get(reverse("shifts_team"), {"department": self.other.pk}).status_code, 403)
        self.assertEqual(self.client.get(reverse("shifts_type_edit", args=[self.night.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("shifts_cell"), {"user": self.support.pk, "date": "2026-10-06", "department": self.department.pk}).status_code, 403)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[self.row.pk]), {"action": "reset"}).status_code, 200)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[make_assignment(self.outsider, self.night, date(2026, 10, 6)).pk]), {"action": "reset"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("shifts_check_in", args=[self.today_row.pk])).status_code, 200)
        for name, payload in (
            ("shifts_cell", {"user": self.support.pk, "date": "2026-10-06", "department": self.department.pk}),
            ("shifts_copy_week", {"department": self.department.pk, "start": "2026-10-03"}),
            ("shifts_repeat_week", {"department": self.department.pk, "start": "2026-10-03", "weeks": "1"}),
            ("shifts_auto_fill", {"department": self.department.pk, "action": "apply", "start": "2026-10-03", "view": "week"}),
            ("shifts_calc_rotation", {"action": "apply", "department": self.department.pk, "shift_type": self.night.pk, "start": "2026-10-05", "end": "2026-10-05"}),
        ):
            self.assertEqual(self.client.post(reverse(name), payload).status_code, 403, name)
        self.assertEqual(self.client.post(reverse("shifts_type_archive", args=[self.night.pk])).status_code, 403)
        self.client.force_login(self.branch)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[self.row.pk]), {"action": "reset"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("shifts_check_in", args=[self.today_row.pk])).status_code, 403)
        for user in (self.manager, self.superuser):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("shifts_home")).status_code, 302)
            for name in manager_gets + shared_gets + support_gets:
                self.assertEqual(self.client.get(reverse(name)).status_code, 200, f"{user.username} {name}")
            self.assertEqual(self.client.get(reverse("shifts_type_edit", args=[self.night.pk])).status_code, 200)
            self.assertEqual(self.client.get(reverse("shifts_cell"), {"user": self.support.pk, "date": "2026-10-06", "department": self.department.pk}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_cell"), {"user": self.support.pk, "date": "2026-10-07", "department": self.department.pk, "shift_type": self.night.pk}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_copy_week"), {"department": self.department.pk, "start": "2026-10-03"}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_repeat_week"), {"department": self.department.pk, "start": "2026-10-03", "weeks": "13"}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_auto_fill"), {"department": self.department.pk, "action": "preview", "start": "2026-10-03", "view": "week"}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_calc_rotation"), {"action": "preview", "department": self.department.pk, "shift_type": self.night.pk, "start": "2026-10-05", "end": "2026-10-05", "users": [self.support.pk]}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[self.row.pk]), {"action": "reset"}).status_code, 403)
            self.assertEqual(self.client.post(reverse("shifts_check_in", args=[self.today_row.pk])).status_code, 403)
```

Run: `python manage.py test shifts.tests.PermissionMatrixTests -v 1`

Expected: FAIL until every view above returns the status this test asserts. Fix the view that returns the wrong status. Do not weaken the test.

Then run the catalog check. The check command is the failing i18n step.

Run: `python scripts/i18n.py check --verbose`

Expected: exit 1 listing the new English msgids that have no Arabic `msgstr`.

- [ ] **Step 2: Update catalogs and docs**

```bash
python scripts/i18n.py update
python scripts/i18n.py compile
```

Fill Arabic `msgstr` values for the new msgids. Do not leave them empty. `scripts/i18n.py check` fails on empty translations. If a msgid already has an Arabic `msgstr` in the catalog, leave that existing translation. For each new empty msgid, use this Arabic text:

| msgid | msgstr |
|---|---|
| Manage Shifts | إدارة المناوبات |
| Shift type | نوع المناوبة |
| Shift types | أنواع المناوبات |
| Start time | وقت البداية |
| End time | وقت النهاية |
| Night | ليلي |
| Colour | اللون |
| Archived | مؤرشف |
| Shift assignment | تعيين مناوبة |
| Shift assignments | تعيينات المناوبات |
| Start override | بداية مخصصة |
| End override | نهاية مخصصة |
| Times set by | الأوقات حددها |
| Times set at | وقت تحديد الأوقات |
| Checked in at | تم تسجيل الحضور في |
| Rota | جدول المناوبات |
| My shifts | مناوباتي |
| Available now | المتاحون الآن |
| Shifts | المناوبات |
| Shift types | أنواع المناوبات |
| Calculator | الحاسبة |
| Team rota | جدول الفريق |
| Start and end must differ. | يجب أن يختلف وقت البداية عن وقت النهاية. |
| Shift type name must be at least 2 characters long. | يجب أن يكون اسم نوع المناوبة حرفين على الأقل. |
| Enter both start and end, or leave both blank. | أدخل البداية والنهاية معاً، أو اتركهما فارغين. |
| Only active support users in this department can be assigned. | يمكن تعيين موظفي الدعم النشطين في هذا القسم فقط. |
| Archived shift types cannot be assigned. | لا يمكن تعيين أنواع المناوبات المؤرشفة. |
| That time does not exist on this date. | هذا الوقت غير موجود في هذا التاريخ. |
| Enter a number of weeks from 1 to 12. | أدخل عدد أسابيع من 1 إلى 12. |
| Nothing to copy. | لا يوجد ما يُنسخ. |
| Copied %(count)s shifts. | تم نسخ %(count)s مناوبات. |
| Repeated %(count)s shifts. | تم تكرار %(count)s مناوبات. |
| Filled %(count)s night shifts. | تم ملء %(count)s مناوبات ليلية. |
| This department has no night shift. | لا توجد مناوبة ليلية لهذا القسم. |
| Nobody available on %(date)s. | لا يتوفر أحد في %(date)s. |
| You can only change hours from the last 7 days onward. | يمكنك تغيير الساعات من آخر 7 أيام فصاعداً فقط. |
| Enter both a start and an end time. | أدخل وقت البداية ووقت النهاية معاً. |
| This shift must be longer than 0 hours and no more than 16 hours. | يجب أن تكون هذه المناوبة أطول من 0 ساعة ولا تتجاوز 16 ساعة. |
| You can check in from 30 minutes before this shift starts. | يمكنك تسجيل الحضور ابتداءً من 30 دقيقة قبل بدء هذه المناوبة. |
| This shift has ended. | انتهت هذه المناوبة. |
| You are not assigned to a department. | لست معيناً في قسم. |
| Nobody on shift now | لا أحد في مناوبة الآن |
| You are on shift until %(end)s. | أنت في مناوبة حتى %(end)s. |
| You have no upcoming shifts. | لا توجد مناوبات قادمة. |
| Set by worker | حدده الموظف |
| Not in this department | ليس في هذا القسم |
| Inactive | غير نشط |
| Not checked in | لم يُسجَّل الحضور |
| Missed | غياب |
| Check in | تسجيل الحضور |
| Clear check-in | إلغاء تسجيل الحضور |
| Set my hours | حدد ساعاتي |
| Reset to shift default | إعادة الضبط إلى وقت المناوبة |
| Copy last week | انسخ الأسبوع السابق |
| Repeat this week forward | كرر هذا الأسبوع للأمام |
| You cannot open this page. | لا يمكنك فتح هذه الصفحة. |
| Empty | فارغ |
| Back-to-back | متعاقبة |
| Checked in at %(time)s | تم تسجيل الحضور في %(time)s |
| A shift that ends before its start is a night shift and runs into the next morning. | المناوبة التي تنتهي قبل بدايتها مناوبة ليلية وتمتد إلى صباح اليوم التالي. |
| This shift overlaps %(name)s on %(date)s (%(start)s–%(end)s). | تتعارض هذه المناوبة مع %(name)s في %(date)s (%(start)s–%(end)s). |
| %(hours)s hours %(minutes)s minutes | %(hours)s ساعة و%(minutes)s دقيقة |
| %(hours)s hours %(minutes)s minutes after midnight. | %(hours)s ساعة و%(minutes)s دقيقة بعد منتصف الليل. |
| Colour must be a 6-digit hex value. | يجب أن يكون اللون قيمة سداسية من 6 أرقام. |
| No department exists. | لا يوجد قسم. |
| Clear the audit fields when the override is cleared. | امسح حقول التدقيق عند مسح الأوقات المخصصة. |
| Record who set the times. | سجّل من حدد الأوقات. |

`{% blocktrans trimmed %}Checked in at {{ time }}{% endblocktrans %}` extracts as `Checked in at %(time)s`. Keep the `%(name)s` placeholders unchanged inside the Arabic string.

In `docs/reference/permissions-matrix.md`, add a Shifts section after Maintenance:

```markdown
## Shifts

| UI label | Field name | What it unlocks |
|---|---|---|
| Manage Shifts | `can_manage_shifts` | Manage shift types, edit the rota, copy and repeat weeks, auto-fill nights, and use the calculator. Superusers can do this without the flag. |
```

In `PROJECT_STANDARDS.md`, add one row to the package table:

```markdown
| `shifts/` | Dated rota, night hours, day-shift check-in, Available now | `shifts/views.py`, `shifts/services.py` |
```

Do not change ticket, KB, or notification behavior while editing those docs.

- [ ] **Step 3: Run the check**

Run: `python scripts/i18n.py check --verbose`

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add shifts/tests.py shifts/views.py locale/ar/LC_MESSAGES/django.po locale/ar/LC_MESSAGES/django.mo docs/reference/permissions-matrix.md PROJECT_STANDARDS.md
git commit -m "Translate shifts strings and document the role flag"
```

## Task 15: Final verification

**Files:** none. This task only runs commands. If a command fails, fix the earlier task that owns the file and make a new commit. Do not weaken a test to go green.

- [ ] **Step 1: Run the shifts and core suites**

Run: `python manage.py test shifts core -v 1`

Expected: `OK` and a line `Ran N tests` with N greater than the core count before this work. Failures in `shifts` or `core.tests.ManageShiftsFlagTests` stop the task.

- [ ] **Step 2: Confirm the diff stays on the allowed list**

Run: `git diff --stat main...HEAD`

Expected: only paths named in the file tree and the “Also modify” list at the top of this plan, plus the spec and this plan. No `tickets/`, `kb/`, `news/`, `notifications/`, `webpush/`, `static/css/modern.css`, `static/css/dark-mode.css`, `static/css/rtl.css`, or `core/session_middleware.py`.

- [ ] **Step 3: Check migrations match the models**

Run: `python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`. This command is not the test runner, so it sees `0023` and `shifts.0001`.

- [ ] **Step 4: DEBUG=0 static check**

`DEBUG=0` refuses to boot when `DEFAULT_SUPERADMIN_PASSWORD` is empty or weak. Use a strong throwaway value:

```bash
DEBUG=0 DEFAULT_SUPERADMIN_PASSWORD='Shifts-Static-Check-2026' python manage.py collectstatic --noinput
```

Expected: exit 0. `staticfiles/staticfiles.json` contains `css/shifts.css` and `js/shifts.js`.

- [ ] **Step 5: Commit only if Step 2–4 forced a code fix**

If nothing changed, do not create an empty commit.
