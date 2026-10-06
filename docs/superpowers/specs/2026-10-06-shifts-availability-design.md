# Shifts & availability

**Status:** Approved by owner Omar (`legendrag`) on 2026-10-06. Implementation plan: `docs/superpowers/plans/2026-10-06-shifts-availability.md`.

**Owner:** Omar (GitHub `legendrag`).

**Date:** 2026-10-06.

**Product:** mlamehticket, the Django help-desk. This spec adds a dated staff rota and a “who is on shift right now” board. It does not change tickets, chat, dashboard, knowledge base, news, or notifications.

## Goal

Support managers need a dated rota per department: who works which shift on which calendar day, including overnight shifts that start one evening and end the next morning. Branch staff need to see, right now, which support workers are on shift and when that shift ends. Support workers need their own upcoming shifts, their own department’s rota, a way to record the real hours they worked on each of their night shifts, and a check-in button for today’s day shift.

The schedule is built on specific dates (this week is not next week). There is no recurring weekly pattern model.

## Context (what the implementation must reuse)

These are the current building blocks. Names below match the code.

| Piece | Where | How shifts uses it |
|---|---|---|
| User | `accounts.User` | `user_type` is `branch` (“Needs Support”) or `support` (“Support Agent”). `department` and `branch` are nullable FKs to `core`. `role` is a nullable FK to `core.Role`. `status` is `active` / `inactive`; `save()` mirrors that onto `is_active`. |
| Role flags | `core.Role` | Boolean fields. `Role.save()` sets every `BooleanField` to true when `name.strip().lower() == "admin"`. Views combine `user.is_superuser` with `user.role.<flag>` (missing role means the flag is off). |
| Role editing | `core/forms.py` `RoleForm`; `templates/core/management/form_partial.html` | Settings Hub role modal. Presets live in the inline `applyRolePreset` script. Django admin is `admin.site.register(Role)` in `core/admin.py` (no field allowlist, so a new boolean appears on its own). |
| Department / Branch | `core.Department`, `core.Branch` | Departments own shift types. Branches do not own shifts and do not get a timezone. |
| Time | `config/settings.py` | `TIME_ZONE` from the environment, default `UTC`. `USE_TZ = True`. One zone for the whole deployment. |
| Shell nav | `templates/base.html` | Authenticated sidebar links use `data-nav-key`, `data-shell-nav="1"`, `hx-get`, `hx-target="#shell-content"`, `hx-swap="innerHTML show:window:top settle:0"`, `hx-push-url="true"`, `hx-trigger="shell-nav"`, `hx-sync="#shell-content:replace"`. Content lands in `#shell-content` (`hx-history-elt`). |
| Active nav after HTMX | `static/js/app-shell.js` `updateActiveNav`, `shellPageKindFromHtml`, `shellPageKindFromDom`, `shellPaneEtag` | Path → `data-nav-key`. Pane id → ETag on shell revalidation. |
| Conditional GET | `core/http_cache.py` | `etag_digest`, `htmx_revalidation_match`, `htmx_not_modified`, `apply_read_etag`. 304 only for an HTMX revalidation that is not history-restore and not `append=true`. |
| Session writes on idle polls | `core/session_middleware.py` `TicketListPollSessionMiddleware` | `SESSION_SAVE_EVERY_REQUEST` is true. A view may set `request.ticket_list_304_defer_session_save = True` on a 304 so an unmodified session is not rewritten more than once a minute. |
| Bounded poll | `templates/tickets/list_live_partial.html` | `hx-trigger="every 20s [...]"` plus `data-no-progress` and `data-etag`. `static/js/loading.js` treats `every` triggers and `data-no-progress` as automatic (no progress bar). Ticket 304 handling in `app-shell.js` is specific to `#tickets-live`; shifts must not extend that ticket path. |
| Local dates vs MySQL | `tickets/template_views.py` `_aware_day_bounds` | Do not filter with `DateTimeField.__date`. With `USE_TZ=True`, MySQL `CONVERT_TZ` returns NULL when timezone tables are missing and the filter matches nothing. |
| i18n | `LANGUAGE_CODE=en`, `LANGUAGES` en/ar, catalogs in `locale/ar` only | `{% load i18n %}`, `{% trans %}`, `{% blocktrans trimmed %}`. No `/ar/` URL prefix. `scripts/i18n.py` updates and compiles the Arabic catalog. `html[dir=rtl]` comes from `base.html` when the language is Arabic. |
| Theme | `static/css/dark-mode.css` | `[data-theme="dark"]` on `<html>`, CSS variables `--panel-bg`, `--text-main`, `--text-muted`, `--border`, `--bg`, `--warning`, `--danger`. |
| Tests | Django `TestCase`, `python manage.py test` | `config/settings.py` disables migrations when `'test' in sys.argv` (`MIGRATION_MODULES`). Schema comes from models. New tests go in the new app’s `tests.py`. |
| DB | `DB_ENGINE=mysql` uses MySQL (`utf8mb4`) via PyMySQL; otherwise SQLite | Production checks run on MySQL/MariaDB. |

## Locked decisions

1. One new Django app, `shifts`. One sidebar entry, label **Shifts**.
2. Dated assignments only. No recurrence model, no cron, no generation of an endless series.
3. A shift that starts Monday 22:00 and ends Tuesday 06:00 is stored on Monday. It stays “Monday’s shift” until Tuesday 06:00.
4. At most one assignment per person per calendar date. Overlapping intervals, including across midnight, are rejected with a validation message. Intervals are half-open: `[start, end)`. Ending at 06:00 and starting the next shift at 06:00 does not overlap.
5. New assignments (and edits on today or later) may only name an **active support user of the shift type’s department**.
6. Managers are `user.is_superuser` **or** `user.role.can_manage_shifts`. A branch user or a support user who has the flag is a manager and is not limited to the branch/support tabs. The flag is enforced on the server for every endpoint.
7. Branch users who are not managers can open only the Available now board. They cannot edit anything, and they never see or POST check-in. Support users who are not managers can open My shifts, Team rota (own department only), and the same Available now board. They cannot open manager URLs. They may POST hours only on their own night-shift assignments, inside the window in decision 19, and they may POST check-in only on their own day-shift assignment for today, inside the window in decision 23.
8. Available now shows the same payload to every viewer: per department, names and that shift’s effective end time. A night-type row is listed while now is inside its effective interval, with no check-in. A day-type row is listed only when `checked_in_at` is set **and** now is inside its effective interval. No start time, shift-type name, phone, email, hours, check-in time, or any other field. No date query parameter changes the window.
9. Week grids start on Saturday in `TIME_ZONE` and run Saturday through Friday. Arabic RTL mirrors layout; it does not move the week start. Month grids stay calendar months (the 1st through the last day) and do not snap to a Saturday. Decision 3 is unchanged: an overnight shift is stored on its start date, whichever weekday that is.
10. Repeat-forward accepts N from 1 through 12 inclusive.
11. Copy, repeat, auto-fill, and the night-rotation apply never overwrite an existing assignment and never skip the overlap rule quietly. Conflicts are listed.
12. Night hours follow the **shift type**, not whether the effective interval crosses midnight. If `shift_type.is_night` is true, every clipped minute of the effective interval is night hours, including a worker entry such as 18:00–23:00 that stays on the same evening. If the shift type is not a night type, every clipped minute is day hours, even when a manager override crosses midnight. Clipping to the selected range still applies. The shift-length tool still shows “hours after midnight” as a separate informational number. That number is not the night-hours total. The rotation suggester counts night-type assignments, one per date, using the same type flag.
13. `ShiftType.is_night` is computed, not typed: true exactly when `end_time < start_time`.
14. Shift-type names are unique per department, including archived rows. Archiving does not free the name.
15. Delete is not offered for shift types. Archive only. `on_delete=PROTECT` so a department, user, or shift type that still has rows cannot be deleted out from under the rota.
16. Times are the deployment `TIME_ZONE` only. Per-branch zones are out of scope. See Edge cases for the DST assumption.
17. Polling exists only on Available now, every 20 seconds, and only while the browser tab is visible. No WebSockets, no Channels consumer, no cache framework, no Celery.
18. A support worker’s real hours for a night shift are the existing per-day `start_time_override` and `end_time_override` on that `ShiftAssignment`. Those overrides are the effective times for Available now, hours, coverage, and overlap. `times_set_by` and `times_set_at` record who last set them. The manager rota and Team rota show a “Set by worker” marker when the setter is not a shift manager.
19. A support user who is not a manager may change times only on an assignment whose `user` is themselves and whose shift type is a night type, and only when `date >= local today - 7 days` (today and any future date included). They cannot change the user, the shift type, or the date. Eight days ago is rejected. Older dates stay read-only for that worker. Managers may still edit any assignment, including dates older than 7 days, through the cell modal.
20. On the mine-hours form, start and end are required. End before start crosses midnight into the next calendar day. The start clock time is always placed on the assignment’s date. Length must be greater than 0 and at most 16 hours. The same half-open overlap rule applies. The cell modal does not use the 16-hour cap, so a manager can still save a longer override there. Every check is server-side. A POST whose assignment id is not the caller’s own row returns 403, as does a day shift or a branch user. A date older than 7 days on this endpoint is a validation error, not a 403.
21. “Reset to shift default” clears both overrides and both audit fields. The worker may reset inside the same 7-day window. Managers may reset any assignment. The assignment row stays.
22. Copy last week, repeat-forward, and auto-fill do not copy worker-entered times. A new copy of those rows uses the shift type’s default times and null audit fields. An override counts as worker-entered when both times are set and `times_set_by` is set and `is_shift_manager(times_set_by)` is false. Manager-set overrides (the setter is a manager, or both times are set and `times_set_by` is null) are copied. The new row’s `times_set_by` is the manager who ran the action, and `times_set_at` is now. Auto-fill already writes the night type’s default times and never writes overrides. None of these actions copy `checked_in_at`. New rows start unchecked.
23. Day shifts have a check-in. Night shifts do not. Only the support user who owns today’s day-shift assignment can press it (`user_type` support). Branch users never see it. Managers do not check in for someone else; they see status on the rota and can clear `checked_in_at` from the manager cell. A manager whose own `user_type` is support and who has today’s day shift sees the button for that shift. The button is allowed only when `date` is the local today and `effective start - 30 minutes <= now < effective end`. Early check-in does not put them on Available now before the effective start. One check-in per assignment; a second POST does not change `checked_in_at`. Workers cannot undo. There is no clear-audit pair: clearing sets `checked_in_at` back to null. Hours and coverage ignore check-in and keep using the scheduled effective interval.

## Data model

App label `shifts`. Both models live in `shifts/models.py`.

### `ShiftType`

Belongs to one department.

| Field | Type | Rules |
|---|---|---|
| `department` | FK `core.Department`, `on_delete=PROTECT`, `related_name="shift_types"` | Required. Same idea as `tickets.Ticket.department`: a department that still has shift types cannot be deleted. |
| `name` | `CharField(max_length=100)` | Required, stripped, at least 2 characters. Unique with `department`. |
| `start_time` | `TimeField` | Required. |
| `end_time` | `TimeField` | Required. Must differ from `start_time`. |
| `is_night` | `BooleanField(default=False, editable=False)` | Set in `save()` to `end_time < start_time`. A form must not expose it as an editable checkbox. The type form shows a read-only “Night” badge when the posted times cross midnight. |
| `colour` | `CharField(max_length=7)` | Required. Validated `^#[0-9A-Fa-f]{6}$`. Default `#6366f1`. Stored with this spelling. |
| `archived` | `BooleanField(default=False)` | Archive hides the type from pickers. It does not delete assignments. |
| `created_at` / `updated_at` | from `core.models.TimeStampedModel` | Subclass that abstract model. Do not copy the fields. |

Constraints and indexes:

- `UniqueConstraint(fields=["department", "name"], name="uniq_shift_type_department_name")`.
- `Index(fields=["department", "archived"])`.

`Meta.ordering = ["department__name", "name"]`. Verbose names wrapped in `gettext_lazy`.

There is no partial unique index. MySQL/MariaDB would ignore `UniqueConstraint.condition`, and this project’s production database is MySQL.

### `ShiftAssignment`

One person, one local calendar date, one shift type, optional per-day times.

| Field | Type | Rules |
|---|---|---|
| `user` | FK `accounts.User`, `PROTECT`, `related_name="shift_assignments"` | Required. |
| `shift_type` | FK `ShiftType`, `PROTECT`, `related_name="assignments"` | Required. |
| `date` | `DateField` | The local calendar date the shift **belongs** to. Not a `DateTimeField`. |
| `start_time_override` | `TimeField(null=True, blank=True)` | Both overrides or neither. This is the worker’s actual start, or a manager’s per-day start. |
| `end_time_override` | `TimeField(null=True, blank=True)` | If set, must differ from the start override. Placed on `date` when `end >= start`, otherwise on `date + 1 day`. |
| `times_set_by` | FK `accounts.User`, `on_delete=SET_NULL`, `null=True`, `blank=True`, `related_name="shift_times_set"` | Who last set the overrides. Null when the row uses the shift type’s times. |
| `times_set_at` | `DateTimeField(null=True, blank=True)` | When those overrides were last set. Null together with `times_set_by`. |
| `checked_in_at` | `DateTimeField(null=True, blank=True)` | Aware instant the owner checked in. Null if they have not, or after a manager clears it. The client never sends this value. No `check_in_cleared_by` or `cleared_at`. |
| `created_at` / `updated_at` | `TimeStampedModel` | A worker save or check-in bumps `updated_at`, so the rota grid ETag changes. |

Constraints and indexes:

- `UniqueConstraint(fields=["user", "date"], name="uniq_shift_assignment_user_date")`. This matches the grid (one cell).
- `Index(fields=["date"])` for Available now (`date__in` yesterday and today).
- `Index(fields=["shift_type", "date"])` for the department grid.

`Meta.ordering = ["date", "user_id"]`.

### Effective interval

Implemented once in `shifts/services.py` and used by validation, Available now, hours, coverage, and overlap.

```text
start_t, end_t = overrides if both set, else the shift type's times
start_dt = aware local datetime on `date` at start_t
if end_t < start_t:
    end_dt = aware local datetime on `date + 1 day` at end_t
else:
    end_dt = aware local datetime on `date` at end_t
interval = [start_dt, end_dt)   # half-open
```

Aware datetimes use `django.utils.timezone.make_aware` and `timezone.get_current_timezone()` (the active `TIME_ZONE`). “Contains now” means `start_dt <= timezone.now() < end_dt`.

`effective_crosses_midnight(assignment)` is `end_t < start_t`. That flag only places the end on the next calendar day. It does **not** decide night hours. Night hours use `shift_type.is_night` (decision 12). A night type with worker times 18:00–23:00 does not cross midnight and is still night hours. A day type with a manager override of 22:00–06:00 does cross midnight and is still day hours.

Equal start and end is a validation error (`"Start and end must differ."`) on the shift type and on a manager override in the cell modal. A single override without the other is `"Enter both start and end, or leave both blank."` The mine-hours form uses the messages in “Worker night hours” below. That endpoint always applies the 16-hour cap. The cell modal does not.

`clean()` also requires the audit pair to match the overrides: both overrides set means both `times_set_by` and `times_set_at` are set; both overrides empty means both audit fields are empty.

### Worker night hours

Constant `WORKER_HOURS_LOOKBACK_DAYS = 7` in `shifts/services.py`.

`shifts_mine_hours` returns **403** unless every permission check below holds:

- the caller is authenticated
- `assignment.user_id == request.user.id` (a different id in the URL is 403, including a manager acting on someone else)
- `assignment.shift_type.is_night` is true (a day shift is 403, not a validation error)
- the caller is a support user, or a shift manager who is that assignee

Check in that order. An archived night type is still editable here; `is_night` is the gate, not `archived`.

A branch user fails the last check and gets 403. Managers change other people’s rows only through `shifts_cell`. A manager who is the assignee may use the mine form on their own night row; `times_set_by` is then a manager, so the “Set by worker” marker stays off and copy will copy those times. The mine endpoint still applies the 7-day window and the 16-hour cap to that manager. A longer span, or a date older than 7 days, is done in the cell modal, which has neither limit.

The POST body is `start_time`, `end_time`, and `action` (`save` or `reset`). Ignore any posted user, date, or shift type. The row id in the URL is the only assignment key.

Save builds the interval with the start on `assignment.date`. If `end_time < start_time`, the end is on the next day. If `end_time > start_time`, the end is on `assignment.date`. Length must be greater than 0 and at most 16 hours (960 minutes). 16 hours exactly is allowed. Then run the same overlap check as managers. On success set the two overrides, `times_set_by` to the caller, and `times_set_at` to `timezone.now()`.

Reset, inside the same window, sets both overrides and both audit fields to null. It does not delete the assignment.

Validation failures re-render that row with HTTP 200 and a translated error (HTMX swaps the row; it does not navigate the shell):

- Missing start or end: `"Enter both a start and an end time."`
- Length not in `(0, 16]` hours: `"This shift must be longer than 0 hours and no more than 16 hours."`
- `date` older than 7 days: `"You can only change hours from the last 7 days onward."`
- Overlap: the existing overlap message.

Date-window failures are validation errors, not 403, so the row can show the sentence. Permission failures stay 403 and do not include the other person’s times.

`overrides_set_by_worker(assignment)` is true when both overrides are set, `times_set_by_id` is set, and `is_shift_manager(times_set_by)` is false. That is the “Set by worker” marker. Manager-set means both overrides are set and the setter is a manager, or both overrides are set and `times_set_by` is null (treated as manager-set so a filled override is not dropped). Copy uses that split; see Copy, repeat, auto-fill.

### Day-shift check-in

Constant `CHECK_IN_EARLY_MINUTES = 30` in `shifts/services.py`.

Check-in applies only when `shift_type.is_night` is false. Night assignments never show a button, never store `checked_in_at`, and never gain a rota check-in marker. Changing a row’s type from day to night clears `checked_in_at`. Changing times does not clear it.

`shifts_check_in` is POST only, CSRF-protected, and returns **403** unless all of these hold, in order:

- the caller is authenticated
- `assignment.user_id == request.user.id`
- `request.user.user_type == support`
- `shift_type.is_night` is false
- `assignment.date == timezone.localdate()`

A branch user, another support user, a manager posting someone else’s id, a night shift, and any assignment that is not today all get 403. The body of a 403 does not include that other assignment. Ignore any posted timestamp or clear flag. This URL cannot clear a check-in.

When those checks pass:

- If `checked_in_at` is already set, return 200 and the same timestamp. Do not write again. This includes a second press after the shift has ended.
- If `checked_in_at` is null and now is outside `[effective_start - 30 minutes, effective_end)`, return 200, leave the field null, and re-render the panel with a hint. Too early: `"You can check in from 30 minutes before this shift starts."` After the end: `"This shift has ended."`
- Otherwise set `checked_in_at = timezone.now()` and return 200.

The panel then shows `"Checked in at %(time)s"` with `H:i` in `TIME_ZONE`, and it does not show the button. Outside the window the button is rendered `disabled` with the same hint, so a normal click never fires. The server still enforces the window.

Managers clear a check-in only from the manager rota cell, with POST `clear_check_in=1` on `shifts_cell`. That sets `checked_in_at` to null and keeps the assignment. It is not offered on Team rota. The owner cannot clear. If a manager clears during the open window, the owner may check in again, and that new press stores a new `timezone.now()`. There is no undo control on My shifts.

### Who may be assigned

On create, and on any update whose `date` is today or later (`date >= timezone.localdate()`):

- `user.user_type == User.UserType.SUPPORT`
- `user.status == User.Status.ACTIVE`
- `user.department_id == shift_type.department_id`
- `shift_type.archived` is false

Failure messages (gettext):

- `"Only active support users in this department can be assigned."`
- `"Archived shift types cannot be assigned."`

Past rows (`date < local today`) may keep a user who has since left the department, become inactive, or changed `user_type`. A manager may correct that past row’s type or times. Changing the past row’s user still requires the new user to be an active support user of the type’s department. Past rows may still display an archived type; they may not be switched onto an archived type.

### Overlap

`clean()`, the cell form, and the mine-hours save, and again inside `transaction.atomic` before every bulk write. Overlap always uses the effective interval, so a worker entry of 18:00–23:00 is compared as 18:00–23:00 and not as the shift type’s default:

1. Reject a second row for the same `(user, date)` with `"This person already has a shift on this date."`
2. Load that user’s assignments on `date - 1 day`, `date`, and `date + 1 day` (exclude the row being saved).
3. If the new half-open interval intersects any of those intervals, reject with `"This shift overlaps %(name)s on %(date)s (%(start)s–%(end)s)."` using the other shift’s type name and local times.

Example: Monday 22:00–06:00 and Tuesday 01:00–09:00 overlap. Monday 22:00–06:00 and Tuesday 06:00–14:00 do not. Monday 09:00–17:00 and Monday 18:00–22:00 cannot both exist, because the unique constraint is one row per date, not because the clock intervals meet.

### Archived types and department changes

- Historic cells (`date < today`) render the type name and colour even when `archived=True`.
- Today and future cells that already point at an archived type keep showing it, with an “Archived” marker. The picker does not offer it. Copy and repeat skip archived source types.
- Today and future cells where the user is no longer an active support user of that department show a “Not in this department” badge (or “Inactive” when the department still matches but `status` is not active). The row stays. It still blocks overlap. It still counts for hours and coverage. A night row still appears on Available now while the interval contains now. A day row appears there only when it is also checked in. The rotation suggester will not pick that user as a new candidate. Nothing is deleted automatically.

## Permissions

Helper `shifts/access.py`:

```python
def is_shift_manager(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    role = getattr(user, "role", None)
    return bool(role and role.can_manage_shifts)
```

`LoginRequiredMixin` (or equivalent) on every view. Anonymous users get the existing login redirect (`LOGIN_URL = "login"`). `accounts.middleware.ForcePasswordChangeMiddleware` is unchanged; shifts URLs are not exempt.

Authorization failures return **403**, not 404, with a short translated notice. Do not render another department’s future grid in the body of a 403.

### Flag

`core.Role.can_manage_shifts`:

```python
can_manage_shifts = models.BooleanField(default=False, verbose_name=_("Manage Shifts"))
```

Place it with the other access flags, after `can_manage_maintenance`.

`Role.save()` already loops `BooleanField`s for the admin name. Do not add a special case. The next save of a role named `admin` (any case, surrounding space ignored) turns this flag on.

Migration `core/migrations/0023_role_can_manage_shifts.py`:

- Depends on `core.0022_alter_i18n_verbose_names`.
- `AddField` default `False`.
- `RunPython` (and a noop reverse) that sets `can_manage_shifts=True` on existing rows whose stripped name lowercases to `admin`. Use the historical model from `apps.get_model`; do not call the live `Role.save()`. Without this, an existing non-superuser admin role would lack the flag until somebody re-saved it. Superusers are managers either way.

Settings UI:

- `RoleForm.Meta.fields` and `widgets`: add `can_manage_shifts` next to the other access flags.
- `templates/core/management/form_partial.html`: one checkbox in the Access `perm-card`, same `<label class="perm-item">` pattern as `can_manage_maintenance`.
- `applyRolePreset`: do **not** add the field to the `support` or `branch` preset lists. `full` uses `setAll(true)`, so it includes the new checkbox without a named entry. `clear` clears it.

`core/admin.py` needs no edit while `Role` stays a default `ModelAdmin`.

Implementation also adds one Shifts row to `docs/reference/permissions-matrix.md` and one package-table line to `PROJECT_STANDARDS.md`. Those files describe current behavior; they are not product features.

### Matrix

| Viewer | Shift types, rota edits, copy, repeat, auto-fill, calculator | My shifts | Set own night hours | Check in | Team rota | Available now |
|---|---|---|---|---|---|---|
| Anonymous | login redirect | login redirect | login redirect | login redirect | login redirect | login redirect |
| Superuser | allow, all departments | allow (own rows; may be empty) | own night rows via the mine form; anyone via the cell modal, any date | only if `user_type` is support and the row is their own day shift today; may clear anyone’s check-in from the cell | allow, any department | allow |
| Role `can_manage_shifts` (any `user_type`) | allow, all departments | allow | same as superuser | same as superuser | allow, any department | allow |
| Support, flag off | 403 | own upcoming rows, plus own night rows back 7 days | own night type only, `date >= today - 7 days`; 403 on any other row | own day shift today only; 403 otherwise; cannot clear | own `user.department_id` only, read-only, with check-in markers | allow |
| Branch, flag off | 403 | 403 | 403 | 403, button not rendered | 403 | allow |
| Support with no department, flag off | 403 | own upcoming rows, plus own night rows back 7 days | same as other support | same as other support | empty state, no department picker | allow |

Support Team rota ignores a requested `department` that is not theirs and returns 403 if the query string tries to switch department. Managers may pass any department id.

Available now lists **every** department’s current names to every logged-in viewer, including branch users and support users. That is the board. It is not scoped to the viewer’s department. It still must not include future days or hours.

## URLs, views, templates

Include in `config/urls.py` next to the other apps:

```python
path("shifts/", include("shifts.urls")),
```

`INSTALLED_APPS` gains `"shifts"` after `"webpush"`. `shifts/urls.py` does not set `app_name`. No urls module in this repo uses a namespace. Reverse names are the global strings in the table below (`reverse("shifts_home")`).

`shifts/urls.py` names:

| Name | Method | Path | View |
|---|---|---|---|
| `shifts_home` | GET | `/shifts/` | Redirect to the default tab. |
| `shifts_rota` | GET | `/shifts/rota/` | Manager rota page. |
| `shifts_rota_grid` | GET | `/shifts/rota/grid/` | Grid partial (ETag). |
| `shifts_cell` | GET, POST | `/shifts/cell/` | Modal: set, replace, or clear one cell. |
| `shifts_copy_week` | POST | `/shifts/rota/copy-week/` | Copy the previous week onto the displayed week. |
| `shifts_repeat_week` | POST | `/shifts/rota/repeat-week/` | Repeat the displayed week forward N weeks. |
| `shifts_auto_fill` | POST | `/shifts/rota/auto-fill/` | Preview or apply night fill for the visible range. |
| `shifts_types` | GET | `/shifts/types/` | Shift type list. |
| `shifts_type_add` | GET, POST | `/shifts/types/add/` | Modal create. |
| `shifts_type_edit` | GET, POST | `/shifts/types/<int:pk>/edit/` | Modal edit. |
| `shifts_type_archive` | POST | `/shifts/types/<int:pk>/archive/` | Set `archived=True`. No delete view. |
| `shifts_calculator` | GET | `/shifts/calculator/` | Four tools on one page. |
| `shifts_calc_hours` | GET | `/shifts/calculator/hours/` | Hours partial. |
| `shifts_calc_rotation` | POST | `/shifts/calculator/rotation/` | Preview or apply. |
| `shifts_calc_length` | GET | `/shifts/calculator/length/` | Length partial. |
| `shifts_calc_coverage` | GET | `/shifts/calculator/coverage/` | Heatmap partial. |
| `shifts_available` | GET | `/shifts/available/` | Available now page. |
| `shifts_available_board` | GET | `/shifts/available/board/` | Polled partial. |
| `shifts_mine` | GET | `/shifts/mine/` | My shifts. |
| `shifts_mine_hours` | POST | `/shifts/mine/<int:pk>/hours/` | Save or reset the caller’s own night-shift times. |
| `shifts_check_in` | POST | `/shifts/mine/<int:pk>/check-in/` | Check in the caller’s own day shift for today. |
| `shifts_team` | GET | `/shifts/team/` | Read-only team rota. |

Default redirect from `shifts_home`:

- manager → `shifts_rota`
- support, not manager → `shifts_mine`
- branch, not manager → `shifts_available`

Query strings:

- Rota and team: `view=week|month` and `start=YYYY-MM-DD`. For `view=week`, normalize `start` to the Saturday of that week: `start - timedelta(days=(start.weekday() - 5) % 7)` (`date.weekday()` is Monday `0` through Saturday `5`). A Wednesday snaps back to the preceding Saturday; a Saturday stays. For `view=month`, normalize to the first of that month. Month view does not snap to Saturday. Missing `start` means the week (or month) that contains `timezone.localdate()`.
- Rota also takes `department=<id>`. Missing department means the first department by name. A bad id is 404.
- Team rota has no department parameter for non-managers. Managers opening Team rota may pass `department`.
- Calculator hours and coverage: `department`, `view`, `start`, same normalization.
- Rotation: POST body `department`, `start`, `end` (inclusive local dates), `shift_type`, `users` (one or more ids), `action=preview|apply`.
- Length: `start` and `end` as `HH:MM` times, no date.
- Cell: POST `user`, `date`, `department`, optional `shift_type` (empty means clear the assignment), optional `start_time_override`, `end_time_override`, optional `reset_times=1`. `reset_times=1` clears the overrides and both audit fields and keeps the assignment. A manager save that sets both overrides also sets `times_set_by` to that manager and `times_set_at` to now. A manager save that changes only the shift type leaves the overrides and the audit fields as they are. The 16-hour cap is not applied here.
- Mine hours: POST `start_time`, `end_time`, and `action=save|reset` to `shifts_mine_hours`. No user, date, or shift-type field.
- Check-in: POST with no time field to `shifts_check_in`. CSRF required. Manager clear is `clear_check_in=1` on `shifts_cell`, not on this URL.

### Templates

Under `templates/shifts/` (project templates, same as `templates/kb/` and `templates/news/`, not an app `templates/` package):

| File | Role |
|---|---|
| `shell.html` | Extends `base.html`. Root node `id="shifts-shell-pane"` with `data-etag`. Tab list. `{% block shifts_body %}`. |
| `rota.html` | Manager page: department select, week/month controls, toolbar, includes `rota_grid.html`. |
| `rota_grid.html` | People × dates table. Used by the rota page, the grid partial, and read-only by team rota. |
| `cell_form.html` | Modal body for `#modal-content`. |
| `types.html` | Per-department list. |
| `type_form.html` | Modal create/edit. |
| `calculator.html` | Four sections. |
| `calc_hours.html` | Partial. |
| `calc_rotation.html` | Preview table and conflict list. |
| `calc_length.html` | Partial. |
| `calc_coverage.html` | Heatmap partial. |
| `available.html` | Page wrapping the board. |
| `available_board.html` | Polled fragment `id="shifts-available-now"`. |
| `mine.html` | My shifts list. The check-in panel sits above the list. Night rows include the hours form. |
| `mine_row.html` | One `<tr id="shift-mine-{{ assignment.pk }}">`. Save and reset swap this row only. |
| `check_in_panel.html` | `id="shifts-check-in"`. Included at the top of My shifts and at the top of the manager rota when the viewer is a support user. |
| `team.html` | Read-only shell around `rota_grid.html`. |

Tab links are real URLs swapped into `#shell-content` with the same HTMX attributes as the sidebar (`hx-target="#shell-content"`, `hx-push-url="true"`, `hx-sync="#shell-content:replace"`). Tabs the viewer may not open are omitted from the HTML **and** 403 on the server.

Tab set:

- Manager: Rota, Shift types, Calculator, Available now, My shifts, Team rota.
- Support, not manager: My shifts, Team rota, Available now.
- Branch, not manager: Available now only.

Follow the settings tab pattern (`role="tab"`, `aria-selected`, keyboard Enter/Space) from `templates/core/settings_content.html`. The shifts page’s own inline script removes leftover body classes (`ticket-detail-page`, `kb-page`, `settings-page`, `dashboard-page`, and the KB variants) the same way that settings pane does, and calls `updateActiveNav` if present.

Cell edits and type add/edit use the existing modal: `hx-target="#modal-content"` and `openModal()`, as in the sidebar password link and `templates/core/management/form_partial.html`. Validation errors re-render that modal with HTTP 200 and `.notice.notice-error` (the project’s HTMX forms swap on 200). A successful cell save returns the grid partial with `HX-Retarget: #shifts-rota-grid` and `HX-Reswap: outerHTML`, and closes the modal the same way other management forms already close it.

### Sidebar

In `templates/base.html`, inside `.sidebar-nav`, after the Knowledge Base link and before Dashboard, add one link:

- `href` and `hx-get`: `{% url 'shifts_home' %}`
- `data-nav-key="shifts"`
- the same `data-shell-nav` / `hx-target="#shell-content"` / `hx-swap` / `hx-push-url` / `hx-trigger="shell-nav"` / `hx-sync` attributes as Tickets
- visible when `user.is_superuser or user.role.can_manage_shifts or user.user_type == 'support' or user.user_type == 'branch'`
- label `{% trans "Shifts" %}`
- `class="active" aria-current="page"` when the path is under `/shifts/`

Django templates treat a missing `user.role` as a failed lookup, so a support or branch user with no role still sees the link.

`static/js/app-shell.js` changes, and only these:

1. `updateActiveNav`: if the path is `/shifts` or starts with `/shifts/`, `key = "shifts"`.
2. `shellPageKindFromHtml` / `shellPageKindFromDom`: recognize `id="shifts-shell-pane"` and return `"shifts"`.
3. `shellPaneEtag`’s id map: `shifts: "shifts-shell-pane"`.

Do not add a new full-page skeleton in `base.html`. The existing default skeleton is enough. Do not change ticket polling, `pause-polling`, or `#tickets-live`.

### Rota screen

When the viewer’s `user_type` is support and they own today’s day-shift assignment, `rota.html` starts with `check_in_panel.html`. That is the landing a support manager gets from `shifts_home`. A branch manager does not get the panel. The panel is the viewer’s own shift, not a control for the department currently selected in the grid. Calculator, shift types, Team rota, and Available now do not include it.

Toolbar (managers, week view and month view):

- Department `<select>` of all departments, ordered by name.
- Previous / next, and a date input. Week view labels the Saturday–Friday range. Previous and next step seven days from that Saturday. Month view shows that calendar month, unchanged.
- A week/month toggle. Switching view keeps the same anchor date.
- **Copy last week** (week view only; hidden in month view).
- **Repeat this week forward** with a number input N (week view only).
- **Auto-fill nights** (both views; the range is the visible dates).

Grid:

- Rows: active support users in the selected department, plus anyone who already has an assignment on a visible date (so a person who changed department still appears on historic and flagged future cells). Order by first name, then username. One query.
- Columns: each date in the week or month. Header is the translated short weekday and the day number.
- Empty cell: a button the manager can activate. Read-only grids (team rota) are not buttons.
- Filled cell: colour as `background-color` from `ShiftType.colour`, type name as text, and times only when an override is set (otherwise the type’s times are in the accessible name, not a second line). When `overrides_set_by_worker` is true, add a small badge `{% trans "Set by worker" %}`. The same badge is on Team rota. It is not shown when a manager set the times, and it is not shown on Available now. Night cells (`shift_type.is_night`) also get class `shifts-cell--night` and a visible “Night” label, even if the worker’s times stay on the same evening. Colour is not the only night signal. Day cells add one small check-in marker, including on Team rota, and never on night cells:
  - `checked_in_at` set, and the date is today or earlier: `{% blocktrans trimmed %}Checked in at {{ time }}{% endblocktrans %}` with `H:i`.
  - Today, `checked_in_at` null, and now is at or after the effective start: `{% trans "Not checked in" %}`.
  - A past date, `checked_in_at` null: `{% trans "Missed" %}`.
  - Today, before the effective start, and not yet checked in: no check-in marker.
  - Future dates: no check-in marker.
- Badges: “Archived”, “Not in this department”, “Inactive”, as defined above.
- Click (managers) opens the cell modal: shift type `<select>` of non-archived types for that department, optional override times, Save, Clear when the cell is filled, and “Reset to shift default” when overrides are set. Reset posts `reset_times=1` and does not remove the assignment. Clear removes the assignment. When the cell is a day shift with `checked_in_at` set, the modal also has “Clear check-in”, posting `clear_check_in=1`. That does not remove the assignment and is not shown for night shifts. The modal is not how a worker sets their own hours or checks in.

Queries for one grid (no per-cell queries):

1. Assignments with `date__gte=first_visible_date - 1 day` and `date__lte=last_visible_date`, `shift_type__department` = selected, `select_related("user", "shift_type")`, `only()` the columns the template prints, including `checked_in_at`. The extra day is for overlap display and for early-hour coverage on the first visible date (the previous day’s overnight). It is not an extra column. On a Saturday–Friday week that previous day is Friday.
2. Users as described, `only("id", "username", "first_name", "last_name", "department_id", "user_type", "status")`.

ETag for `shifts_rota_grid` and the shell pane: `etag_digest` of language, department id, view, start, assignment count, max `updated_at` of those assignments, and max `updated_at` of the department’s shift types. Use `htmx_revalidation_match` / `htmx_not_modified` / `apply_read_etag`. Do not set `ticket_list_304_defer_session_save` on rota GETs; they are not a 20s poll.

### Copy, repeat, auto-fill

All three are manager POSTs, CSRF-protected, `transaction.atomic`, department-scoped.

**Copy last week.** For each date D in the displayed Saturday–Friday week, look at D−7 days. If that source row’s type is archived, skip it (“archived shift type”). If the target user already has a row on D, skip it (“already assigned”). If the copied interval would overlap a neighbor, skip it (“overlaps …”). Otherwise create the same user and type on D with `checked_in_at` null. Times follow decision 22: worker-entered overrides are not copied, and the new row uses the shift type defaults with null audit fields. Manager-set overrides are copied, with `times_set_by` set to the manager who clicked copy and `times_set_at` set to now. Overlap for that check uses the times that will actually be written. Source Friday’s overnight tail is not copied onto target Saturday; Saturday’s cell comes only from the previous Saturday. The overlap check still sees that Friday-night tail, using Friday’s effective interval (worker times included when that source row is the neighbor, not when it is the row being copied).

**Repeat this week forward.** N is an integer 1–12. Anything else is a form error `"Enter a number of weeks from 1 to 12."` For k = 1..N, copy each displayed Saturday–Friday assignment onto `date + 7*k days` with the same skip rules, the same worker-versus-manager time rule, and a null `checked_in_at`, including rows created earlier in this same transaction. Process dates in Saturday-to-Friday order so a copied Friday night exists before the next week’s Saturday is checked. Auto-fill does not write overrides at all.

**Auto-fill nights.** Same algorithm as calculator tool 2, with these fixed inputs: the selected department, the visible date range, people = all active support users currently in that department, and a night shift type.

- No non-archived night type: notice `"This department has no night shift."` and no writes.
- Exactly one: run preview immediately.
- More than one: the button opens a modal to pick the type, then previews.

Apply uses the same POST with `action=apply`. Preview writes nothing.

Each action returns the grid plus a `.notice` that counts created rows and lists every skip (person, date, reason). Zero created and zero skipped source rows: `"Nothing to copy."` Success with no skips: `"Copied %(count)s shifts."` (repeat and auto-fill use their own translated sentences with a count).

### Shift types screen

Department select, then a table of that department’s types: name, times, Night badge, colour swatch, archived state, Edit, Archive.

Archive is a POST. It sets `archived=True`. It does not remove assignments. There is no separate Unarchive button. The edit form includes the archived checkbox, so clearing it and saving is how a manager restores a type. The list shows archived rows at the bottom, styled muted, so managers can still open them.

The add/edit form: department (fixed to the current list filter on create), name, start, end, colour (`input type="color"` plus the hex check), archived checkbox on edit only. The night badge updates from the posted times after save. Help text: `"A shift that ends before its start is a night shift and runs into the next morning."` Equal times are rejected and do not set `is_night`.

### My shifts

`shifts_home` sends a support user who is not a manager here, so this page is their Shifts landing. Above the list, include `check_in_panel.html` when the viewer’s `user_type` is support. The panel is a `.panel` with one primary `.btn` labeled `{% trans "Check in" %}`. It is rendered only for today’s day-shift assignment. Night shifts render no panel. The form is POST, CSRF, no time input:

```html
<form hx-post="{% url 'shifts_check_in' assignment.pk %}"
      hx-target="#shifts-check-in"
      hx-swap="outerHTML">
```

HTMX replaces only `#shifts-check-in`. It does not target `#shell-content` and it does not add a second poll. Styles stay on `.btn` / `.btn.primary` / `.panel` from `static/css/modern.css`. Any extra layout is in `static/css/shifts.css` under `#shifts-shell-pane`, with logical properties and the existing colour variables, so dark mode and `html[dir=rtl]` work without editing `modern.css`, `dark-mode.css`, or `rtl.css`. After a successful check-in the panel text is `{% blocktrans trimmed %}Checked in at {{ time }}{% endblocktrans %}`.

Rows are the logged-in user’s assignments, ordered by date:

- every assignment with `date >= local today`
- plus that user’s night-type assignments with `date >= local today - 7 days` and `date < local today`

No other people’s rows. A banner still shows when an effective interval contains `timezone.now()`: `"You are on shift until %(end)s."` The end time is the effective end. Each row shows date, type name, colour, effective times, and the Night label when `shift_type.is_night`. Day-type rows are read-only. Empty (nothing in that set): `"You have no upcoming shifts."`

Each night-type row in that set has an inline “Set my hours” form, not a modal and not a full-page post. The row is `mine_row.html`. The form uses the existing `.form-group` and `.btn` / `.btn.primary` / `.btn.secondary` styles from `static/css/modern.css`. The heading is `{% trans "Set my hours" %}`. Two `type="time"` inputs (`start_time`, `end_time`), prefilled with the effective times, a Save button (`action=save`, `{% trans "Save" %}`), and a Reset button (`action=reset`, `{% trans "Reset to shift default" %}`). The form is:

```html
<form hx-post="{% url 'shifts_mine_hours' assignment.pk %}"
      hx-target="#shift-mine-{{ assignment.pk }}"
      hx-swap="outerHTML">
```

HTMX swaps only that `<tr>`. It does not target `#shell-content`. Layout for the inline inputs lives in `static/css/shifts.css`, scoped under `#shifts-shell-pane`, using logical properties and the existing colour variables so dark mode and `html[dir=rtl]` work without editing `modern.css`, `dark-mode.css`, or `rtl.css`. Night rows older than 7 days are not on this page. A forged POST for one still returns the date-window validation error.

### Team rota

Same grid component as the manager rota, `readonly=True`: no toolbar actions, no cell modal, no type management, no check-in button, and no “Clear check-in”. The “Set by worker” badge and the day-shift check-in markers still render. Workers do not edit the team grid; they set hours only on My shifts and check in only from the panel. Non-managers are pinned to `request.user.department`. If that FK is null, render `"You are not assigned to a department."` and no grid. Managers may pick a department.

### Available now

Page plus `available_board.html`:

```html
<div id="shifts-available-now"
     hx-get="{% url 'shifts_available_board' %}"
     hx-trigger="every 20s [!document.hidden]"
     hx-swap="outerHTML"
     data-no-progress
     data-etag="{{ board_etag }}">
```

One card per department, departments ordered by name. Card title is the department name. Body is a list of people on shift: display name and end time. Display name is first name plus last name, trimmed, falling back to `username`. End time is 24-hour `H:i` in `TIME_ZONE`. Empty department: `"Nobody on shift now"`. The region is `aria-live="polite"`. A 304 does not swap, so unchanged polls do not re-announce.

Who is on shift: load assignments with `date__in=[local_yesterday, local_today]` (Python dates, then a `DateField` lookup — not `__date` on a datetime). `select_related("user", "shift_type", "shift_type__department")`. `times_set_at` and `checked_in_at` are columns on the assignment and are used in the ETag, not rendered. In Python, keep a night-type row when its effective interval contains `timezone.now()`. Keep a day-type row only when `checked_in_at` is not null and that same interval contains `timezone.now()`. Group by `shift_type.department`. A day shift that has started but is not checked in is omitted. A day shift checked in during the 30 minutes before the effective start stays omitted until that start. It drops off at the effective end. A night shift never consults `checked_in_at`. Worker-entered 18:00–23:00 on a night type is on shift from 18:00 until 23:00 and not at 23:00. Include yesterday’s overnight night shift when that effective end is still after now. Do not include tomorrow. A shift that ends at the current minute is already over. The board still shows only the display name and the effective end time. It does not show “Checked in”, “Missed”, or a start time.

`static/js/shifts.js` (loaded only from the shifts shell via `{% block extra_js %}` and `{% static 'js/shifts.js' %}`):

- On `htmx:configRequest`, if the element id is `shifts-available-now` and it has `data-etag`, set `If-None-Match`.
- On `htmx:beforeSwap`, if the target id is `shifts-available-now` and the status is 304, set `shouldSwap = false` and `isError = false` (same idea as the `#tickets-live` handler, but in this file).
- On `visibilitychange`, when `document.hidden` becomes false, trigger one refresh of `#shifts-available-now` so the board does not sit stale for up to 20 seconds. That is still a single bounded request, not a second timer.

The view builds the ETag with `etag_digest` of the language, the max `checked_in_at` (or empty) and the count of non-null `checked_in_at` among yesterday’s and today’s assignments, and, per department id, the sorted `(user_id, effective_start_isoformat, effective_end_isoformat, times_set_at_isoformat or "", checked_in_at_isoformat or "")` tuples for rows that pass the on-shift rule above. Changing an override or a check-in changes this digest. An early check-in, before the person is listed, still changes it because of the max and the count. There is no extra poll for check-in. The existing 20-second board poll picks the change up. Same helpers as the ticket list: `htmx_revalidation_match`, `htmx_not_modified`, `apply_read_etag`. On the 304 path only, set `request.ticket_list_304_defer_session_save = True` so idle polls reuse `TicketListPollSessionMiddleware` instead of rewriting the session every 20 seconds. Do not modify `core/session_middleware.py`. The flag name is historical; the middleware already honors it for any view that sets it.

Ignore extra query parameters. The HTML must not contain start times, type names, colours, phone numbers, or hour totals. Tests assert that.

## Calculator

Managers only. One page, four tools, each posting or getting its own partial so a long heatmap does not redo the others. All four call the same interval helpers. Math is in Python (`shifts/services.py`), not in the browser, so tests can lock it.

### 1. Hours per person

Inputs: department, week or month (same `view` and `start` as the rota).

Check-in does not change this tool. A day shift that was missed still counts its scheduled effective minutes. For every assignment of that department whose **effective** interval overlaps `[range_start, range_end)` — `range_end` is the start of the day after the last visible date — clip the interval to that window. Classify by the shift type, then count only the clipped minutes:

- If `shift_type.is_night`, every clipped minute is **night hours**. None of them are day hours. A worker entry of 18:00–23:00 on a night type is 5 night hours.
- If the shift type is not a night type, every clipped minute is **day hours**, even when the effective interval crosses midnight.
- **Total** is day + night. A single shift contributes to only one of those two columns.

A Friday 22:00–06:00 **night type** (8 clock hours) clipped to the Saturday–Friday week that contains that Friday counts only 22:00–00:00: 2 night hours and 0 day hours. The 00:00–06:00 tail falls on the next Saturday. Clipped to that following week, the tail is 6 night hours and 0 day hours. Clipped to a month that contains both Friday and the following Saturday, all 8 hours are night hours. The same clip rules apply when the worker replaced 22:00–06:00 with other times: count the effective interval, still all as night hours. A day type 09:00–17:00 is 8 day hours. A day type 00:00–08:00 is 8 day hours. A day type whose manager override is 22:00–06:00 counts those clipped minutes as day hours.

Show one row per person who has a non-zero clipped total, display name, day, night, and total, as hours and minutes (compute in integer minutes; do not use floats). Omit people with no assignments in range.

### 2. Night-rotation suggester

Inputs: department, inclusive start date, inclusive end date, one non-archived night `ShiftType` in that department, and a non-empty subset of that department’s active support users.

Constant `NIGHT_ROTATION_LOOKBACK_DAYS = 14` in `shifts/services.py`.

Algorithm, deterministic:

1. `dates` = each local date from start through end inclusive.
2. Lookback night count for each included person = how many of their existing assignments in `[start - 14 days, start)` have `shift_type.is_night`. Also record the latest such date, or none. A night type whose worker entered 18:00–23:00 still counts as one night. A day type does not, even if a manager override crosses midnight. This score counts night-type assignments, one per date. It does not use the hours tool’s minute totals.
3. `proposed` starts empty. Walk `dates` in order.
4. A person is a candidate on D when all of these hold:
   - they have no existing assignment on D
   - they have no proposed assignment on D
   - the target type’s interval on D does not intersect their existing or proposed intervals (check D−1, D, and D+1)
   - they are still in the included set
5. Prefer candidates who were **not** on a night-type assignment (existing or already proposed) on D−1. If that set is empty, allow a back-to-back candidate and mark the proposal `back_to_back=True`. If that set is also empty, record a gap for D and continue. “On a night” means the shift type is a night type, not that the effective times cross midnight.
6. Among the remaining candidates, pick the lowest `(lookback nights + nights already proposed in this run)`. Tie-break: earliest last night date (no night yet sorts first), then lowest `user.id`.
7. Propose that person on D with the type’s own times (no overrides).

Preview renders a table: date, person, and a “Back-to-back” note when flagged, then a gap list `"Nobody available on %(date)s."` Preview does not write.

Apply, in one transaction, re-checks each proposal:

- existing row on that user+date → skip `"already assigned"`
- interval overlap → skip with the overlap message
- user no longer an active support user of the department, or type archived or not a night type → skip with the assign/archive message

Insert the rest. Do not delete or update existing rows. The response shows created count and the skip list (person, date, reason). Partial apply is intentional: a race with the grid does not roll back the rows that were still free.

Fairness the tests lock:

- Empty range, 3 eligible people, 6 dates, no lookback, no existing rows: each person gets 2 nights, and nobody has two consecutive dates.
- 2 people, 2 consecutive dates: one each, not the same person twice.
- 1 person, 2 consecutive dates: both proposed, the second marked back-to-back.
- A date that already has any assignment for every candidate: that date is a gap or a skip, and the existing row is unchanged.

### 3. Shift length

Inputs: start time and end time, no date. This tool does not consult the database.

- Equal times: error `"Start and end must differ."`
- End after start: total = end − start, hours after midnight = 0.
- End before start: total = (24:00 − start) + end, hours after midnight = end − 00:00.

Show `"%(hours)s hours %(minutes)s minutes"` and `"%(hours)s hours %(minutes)s minutes after midnight."`

“Hours after midnight” is informational only. The owner asked the length tool to show the overnight portion of a start/end pair. It is not the night-hours figure from tool 1. A 22:00–06:00 pair is 8 hours total and 6 hours after midnight here. Tool 1 counts all 8 hours as night hours only when that assignment’s shift type is a night type and the whole interval sits inside the selected range. The same clock pair on a day type is 8 day hours in tool 1.

### 4. Coverage gaps

Inputs: department, week or month.

Columns are the visible dates. Rows are local hours 00 through 23. A person covers hour H on date D when their interval overlaps `[D H:00, D H+1:00)`. A shift ending at 06:00 does not cover the 06:00 hour. Yesterday’s overnight (assignment date = first column − 1 day) covers the early hours of the first column. On a Saturday–Friday week, that is Friday night covering Saturday’s 00 through 05 rows (the half-open interval that ends at 06:00). The last column’s overnight hours that fall on the next calendar date are not extra columns; they simply do not appear. Month columns stay the calendar month.

Coverage uses the schedule, not check-ins. A day shift with `checked_in_at` null still fills every hour of its effective interval. The heatmap is headcount from the effective interval, not the hours tool’s day/night split, and not the Available now rule. A worker entry of 18:00–23:00 covers hours 18 through 22 only. A crossing night type covers every hour its effective interval overlaps, including hours before midnight on the start date. Whether those occupied minutes are night hours in tool 1 depends on `shift_type.is_night`, not on the heatmap.

Cell text is the count. Count 0 uses class `shifts-gap` (highlighted) and the text `0`, so colour is not the only signal. The heatmap query is the same assignment fetch as the grid, including the day before the range.

## Performance

- In-shell navigation only, as specified above. No full page reload is required for tabs, cell saves, check-in, or the board poll.
- ETag/304 via `core/http_cache.py` on the rota grid (and the shifts shell pane) and on the Available now board. Digest the values listed above, including check-in max and count on the board. Do not hash the whole HTML by rendering twice unless that is cheaper, which it is not. Check-in does not add a timer.
- `select_related` / `only` as specified. The grid and the board must not query inside a row loop. Tests can assert query counts with `assertNumQueries` on the grid and board views (a small fixed budget, not “whatever the template does”).
- The only `every` poll in the app’s new templates is the 20s Available now trigger, gated on `!document.hidden`, with `data-no-progress`.
- No new WebSocket, no `CHANNEL_LAYERS` change, no Django cache, no Redis.
- Available now 304 sets the existing session-defer flag. Rota 304 does not.

## UI, responsive, accessibility, RTL

Match existing components. Do not restyle Tickets, Dashboard, or Settings.

Reuse classes from `static/css/modern.css`: `.panel`, `.btn`, `.btn.primary`, `.btn.secondary`, `.btn.danger`, `.table-wrap`, `.notice`, `.notice-error`, `.badge`, `.settings-tabs`, `.settings-tab`, `.form-group`, `.form-actions`, modal classes already on `#modal-container`.

New rules live only in `static/css/shifts.css`, loaded from the shifts shell with `{% static 'css/shifts.css' %}`. This matches `static/css/` and `static/js/` used by every other page. Do not put a second static tree inside the app. Scope under `#shifts-shell-pane`. Use the existing variables (`--panel-bg`, `--text-main`, `--text-muted`, `--border`, `--bg`, `--warning`, `--danger`) so `[data-theme="dark"]` from `dark-mode.css` applies without editing that file. Do not edit `static/css/modern.css`, `dark-mode.css`, `rtl.css`, or `style.css`.

Shift-type colour stays the manager’s hex in both themes. Night cells add a 2px dashed outline (`shifts-cell--night`) and the word “Night”, because two types can have similar colours. Gaps use `var(--danger)` at low emphasis plus the digit 0.

Responsive:

- The grid sits in `.table-wrap` and scrolls horizontally. The person column is `position: sticky; inset-inline-start: 0` with the panel background.
- Toolbar wraps. Department select is full width under 720px.
- Available now cards are a single column under 720px and a wrapping row of cards above that.
- Cell buttons have at least 44px of block size.

Accessibility:

- Tabs: `role="tablist"` / `role="tab"` / `aria-selected`.
- Each rota cell button’s accessible name includes the person, the date, and either “Empty” or the type name plus “Night” when applicable.
- Heatmap cells expose the count as text.
- The board is `aria-live="polite"`.
- Colour inputs and time inputs have `<label>`s.
- Archive and repeat use the existing confirm pattern only if the action can discard nothing silently; copy/repeat/auto-fill already preview or report skips, so they do not need a second confirm beyond the rotation preview.

RTL:

- Do not set `left` / `right` or `margin-left` / `margin-right` in `shifts.css`. Use logical properties (`margin-inline`, `padding-inline`, `inset-inline-start`).
- Do not force `direction: ltr` on the grid. `html[dir=rtl]` from `base.html` (and `rtl.css`) mirrors the table. Saturday stays the first date in DOM order; in Arabic it appears on the right. Month columns stay in calendar order and mirror the same way.
- Every user-visible string is `{% trans %}` or `{% blocktrans trimmed %}`. Run `python scripts/i18n.py update` and `compile` in the implementation PR so `locale/ar/LC_MESSAGES/django.po` and `.mo` contain the new msgids. English remains the source language.

Times on the rota, the board, and My shifts render with the `H:i` format (24-hour). Dates use Django’s localized date filters.

## Edge cases

| Case | Behavior |
|---|---|
| Midnight-crossing shift | Stored on the start date. The interval runs until `end_dt`. Available now checks yesterday and today. A night type is listed with no check-in. A day type is listed only after check-in and only inside the interval. |
| Touching endpoints | `[22:00, 06:00)` and `[06:00, 14:00)` do not overlap. |
| Two shifts the same calendar day | Blocked by the unique constraint even if the clocks would not overlap. |
| Overlap from yesterday’s night into today | Blocked with the overlap message. |
| Archived type on a past date | Still shown, name and colour. |
| Archived type on a future date that was assigned before archive | Still shown, “Archived” badge. Not offered for new cells. |
| User changes department | Past cells unchanged and not badged. Today and future cells badged “Not in this department”, kept, still blocking overlap. A night row stays eligible for Available now until it ends. A day row stays eligible only if it is also checked in. |
| User deactivated | Same badge rules, worded “Inactive” when the department still matches. They cannot be newly assigned. |
| Department with nobody on shift | That card reads “Nobody on shift now”. Other departments still render. |
| Support user with no department | My shifts still works. Team rota shows the empty-department sentence. |
| Copy onto a filled cell | Skip, listed, existing row unchanged. |
| Repeat N outside 1–12 | Form error, no writes. |
| Rotation vs an existing cell | Preview shows a gap or the apply step lists a skip. The existing assignment is not replaced. |
| All candidates would work back-to-back | Allow it, mark those proposals, do not fail the whole range. |
| DST | Assumption: this deployment uses one `TIME_ZONE` and does not rely on per-branch zones. Default is `UTC`, which has no DST. If `TIME_ZONE` is a zone with DST, intervals follow that zone’s `zoneinfo` rules with no extra compensation (a crossing shift can be 7 or 9 clock hours on the transition). Those clock hours are night hours only when the shift type is a night type. A start or end that lands in a missing local hour raises `"That time does not exist on this date."` Ambiguous times use Django’s default `make_aware` (first occurrence). The length tool has no date, so it is pure clock arithmetic and ignores DST. Its “hours after midnight” figure is not the night-hours total. |
| MySQL timezone tables | Filter `ShiftAssignment.date` with `date__gte`, `date__lte`, and `date__in` only. Build “today” and “yesterday” in Python with `timezone.localdate()`. Do not use `__date`, `TruncDate`, or `CONVERT_TZ` lookups on datetimes. |
| Equal start and end | Validation error, nothing saved. |
| Colour not a 6-digit hex | Validation error. |
| Manager is a branch user | Treated as a manager on every shifts endpoint. |
| Admin role | Migration backfill plus `Role.save()` keep `can_manage_shifts` true. Other existing roles stay false. |
| Week boundary | The rota week is Saturday–Friday. Friday night’s tail falls on Saturday of the next week. Copy does not turn that tail into a Saturday assignment. |
| Night hours vs length tool | Night-type assignments count every clipped effective minute as night hours, even when the worker’s times do not cross midnight. Day-type assignments count every clipped minute as day hours, even when they do cross midnight. The length tool’s “hours after midnight” is a separate informational number. |
| Worker hours 18:00–23:00 | Effective interval is that same evening. Available now includes the person from 18:00 until 23:00 and not at 23:00, with no check-in, because the type is a night type. Hours tool counts 5 night hours. Overlap uses 18:00–23:00, not the type default. |
| Day shift not checked in | Hidden on Available now even after the effective start. Hours and coverage still count the scheduled interval. Today’s rota cell says “Not checked in” once the start has passed. A past day cell says “Missed”. |
| Early check-in | Allowed from 30 minutes before the effective start. `checked_in_at` is set. Available now stays empty for that person until the effective start, then shows them until the effective end. |
| Check-in after the end | Rejected. `checked_in_at` stays null. The panel shows “This shift has ended.” |
| Second check-in | Same `checked_in_at` as the first press. |
| Manager clears check-in | `checked_in_at` becomes null. The worker has no clear control. If the window is still open they may check in again. |
| Copy and check-in | The new row’s `checked_in_at` is null. |
| Worker edits someone else’s id | 403. The response does not include that other assignment’s times. |
| Day shift hours POST | 403. |
| Hours 8 days ago | Validation error `"You can only change hours from the last 7 days onward."` The assignment is unchanged. Seven days ago is accepted. |
| Reset | Clears overrides and `times_set_by` / `times_set_at`. Later calculations use the shift type’s times. |
| Copy of worker times | The new row uses the shift type defaults. A manager-set override on the source is copied, and the new row records the manager who ran the copy. |

## Testing

New tests in `shifts/tests.py` using Django `TestCase` and the test client. Build users with explicit `user_type`, `department` or `branch`, `status`, and a `Role`. Migrations do not run under `manage.py test`; cover `Role.save()` and model `clean()` directly. The `RunPython` admin backfill is checked by reading the migration, not by the test runner.

Unit and view tests:

- Available now includes a night-type Monday 22:00–06:00 assignment when `timezone.now()` is Tuesday 05:00, with `checked_in_at` null, and excludes it at Tuesday 06:00. Freeze time with `django.utils.timezone` override. A day shift is not listed on that rule alone.
- Available now ignores a shift that starts later today.
- A department with no covering assignment renders “Nobody on shift now”.
- Overlap: adjacent night vs early morning rejected; touching endpoints allowed; second row the same date rejected.
- Department and user-type checks: branch user, support user of another department, and inactive support user cannot be assigned on a future date. A past assignment remains after the user’s department changes, and the future one is flagged in the rota HTML.
- Archived type still rendered on a past date; POST of that type onto a future empty cell fails.
- Week start: `view=week` with a Wednesday `start` normalizes to the preceding Saturday; a Saturday `start` stays that Saturday; `view=month` still normalizes to the first of the month. The week label runs Saturday through Friday. Copy last week reads and writes that span and does not create a Saturday assignment from the previous Friday’s overnight tail. Repeat-forward processes Saturday through Friday so the copied Friday night is visible to the next Saturday’s overlap check.
- Hours: a night-type 22:00–06:00 shift inside a range that contains both the start date and the following morning is 0 day hours and 8 night hours (480 minutes). Clipped to the Friday of a Saturday–Friday week, that shift is 2 night hours (120 minutes) and 0 day hours. Clipped to the following Saturday only, it is 6 night hours (360 minutes) and 0 day hours. A night type with worker times 18:00–23:00 inside the range is 5 night hours (300 minutes) and 0 day hours. A day type 09:00–17:00 is 8 day hours. A day type 00:00–08:00 is 8 day hours. A day type with a 22:00–06:00 override counts those minutes as day hours.
- Length tool: 22:00–06:00 → 8 hours total, 6 after midnight. 09:00–12:30 → 3 hours 30 minutes, 0 after midnight. Equal times → error. The after-midnight figure stays informational and is not asserted as the hours-tool night total.
- Rotation fairness cases listed in tool 2, including “does not change an existing assignment”. Lookback scoring counts night-type assignments, including a night type whose effective times do not cross midnight.
- Coverage: the 05:00 hour on Tuesday is covered by Monday’s night shift; the 06:00 hour is not; an hour with no row has text `0` and class `shifts-gap`. A worker entry of 18:00–23:00 covers 18 through 22 and not 23.
- Worker hours: the assignee can save 18:00–23:00 on their own night shift; `times_set_by` is themselves and `times_set_at` is set. POST of another user’s assignment id returns 403 and does not change that row. POST of a day-shift assignment returns 403. `date == today - 8 days` returns the 7-day validation error and does not save. `date == today - 7 days` saves. A crossing entry such as 18:00–02:00 saves, ends the next day, and is at most 16 hours. 18:00–18:00 and a span over 16 hours return the length error. An entry that overlaps a neighbor is rejected with the overlap message and does not save. Reset clears overrides and both audit fields. Available now includes that worker from 18:00 until 23:00 and excludes them at 23:00. Copy last week of a worker-entered row creates the new day with the shift type’s times and null audit fields; copy of a manager-set override copies the times and sets `times_set_by` to the manager who copied. The Available now ETag changes after the override is saved. A branch user POST to `shifts_mine_hours` returns 403.
- Permissions: for every named URL, assert status for anonymous (redirect to login), branch non-manager, support non-manager, support non-manager of another department (team rota and rota GET with `department=`), manager (`can_manage_shifts` and not superuser), and superuser. Branch responses for rota, types, calculator, mine, and team are 403 and the body does not contain another day’s schedule or an hour total. Support POST to cell, copy, repeat, auto-fill, type archive, and rotation apply is 403.
- Available now HTML for a branch user contains the on-shift display name and end time and does not contain the shift type name or the start time.
- ETag: GET the board with `HTTP_HX_REQUEST=true`, then repeat with `HTTP_IF_NONE_MATCH` equal to the `ETag` header, and assert 304 and an empty body. A changed assignment returns 200. A history-restore header (`HTTP_HX_HISTORY_RESTORE_REQUEST=true`) returns 200, matching `htmx_revalidation_match`.
- Check-in: the button is in the HTML only for the owning support user on today’s day shift, on My shifts and on the rota landing when that owner is a support manager. It is absent for a branch user, for another support user, and for a night shift. POST outside the window leaves `checked_in_at` null and returns the hint. A second POST keeps the original timestamp. Available now hides a started day shift until check-in, shows that person after check-in while now is inside the interval, hides them at the effective end, and does not show them before the effective start even when they checked in early. A night-shift worker stays listed with no check-in of their own. The board ETag changes after check-in, including an early check-in that does not yet list the person. A manager `clear_check_in=1` sets `checked_in_at` null. The owner’s POST cannot clear. A branch POST to `shifts_check_in` returns 403. Hours and coverage for that day shift are the same before and after check-in.
- Admin role: `Role(name="admin").save()` sets `can_manage_shifts` True. A role named `Support` saves the flag as given.
- Grid query count stays within the budget asserted in the test (no N+1).

MySQL/MariaDB (test agent, not the unit-test default SQLite):

- Run the shifts tests and the existing suite against `DB_ENGINE=mysql` with `USE_TZ=True` and without loading MySQL timezone tables. Assignment filters on `date` must still return the overnight row. This is the regression that `__date` on a `DateTimeField` would fail.

`DEBUG=0` static check:

- `collectstatic` with `CompressedManifestStaticFilesStorage` succeeds, and the shifts shell’s `{% static 'css/shifts.css' %}` and `{% static 'js/shifts.js' %}` resolve in the manifest. Those files live in the existing `STATICFILES_DIRS` entry `static/`. Do not add another `STATICFILES_DIRS` entry and do not add an app `static/` package.

Manual browser checks (implementation PR, before merge):

- Open Shifts as a manager, a support user, and a branch user. Confirm the tab set.
- Set a night shift, refresh Available now, hide the tab, confirm the poll pauses, show the tab, confirm one refresh.
- Toggle dark mode (`[data-theme="dark"]`) and switch language to Arabic (`dir=rtl`). The grid, cards, and modal must remain usable.
- Regression: Tickets list still polls, Settings role form still saves, Knowledge Base and Dashboard links still navigate inside `#shell-content`. No shifts string appears on those pages.

## Out of scope

- Payroll, overtime pay, or exporting hours to a pay system.
- Employee shift-swap requests or approvals.
- Leave management.
- Notifications or reminders about shifts (no email, no in-app notification, no web push).
- Real-time online presence (“logged in now”).
- Per-branch timezones.
- External calendar sync.
- Mobile app changes, new native clients, or PWA manifest changes.
- WebSockets or any edit under `tickets/`, `notifications/`, `news/`, `kb/`, `webpush/`, or dashboard views.

## Files the implementation may touch

Allowed:

- New tree `shifts/` only: `__init__.py`, `apps.py`, `admin.py`, `models.py`, `services.py`, `access.py`, `forms.py`, `views.py`, `urls.py`, `tests.py`, `migrations/__init__.py`, `migrations/0001_initial.py` (depends on `core.0023` and `accounts.0008_alter_requires_password_change_verbose`). One `views.py` and one `tests.py`, matching `kb` and `news`. No `app_name` on `shifts/urls.py`; this repo does not namespace URLs. No `views/` or `tests/` package. No app-level `templates/` or `static/`. `checked_in_at` is a nullable datetime on `ShiftAssignment` in that initial migration. Do not add check-in clear-audit fields.
- `templates/shifts/` for every shifts template (`shell.html`, `rota.html`, `rota_grid.html`, `cell_form.html`, `types.html`, `type_form.html`, `calculator.html`, `calc_hours.html`, `calc_rotation.html`, `calc_length.html`, `calc_coverage.html`, `available.html`, `available_board.html`, `mine.html`, `mine_row.html`, `check_in_panel.html`, `team.html`). Same place as `templates/kb/` and `templates/news/`.
- New files `static/css/shifts.css` and `static/js/shifts.js` only. Do not edit `modern.css`, `dark-mode.css`, `rtl.css`, or `style.css`.
- `core/tests.py`: add the `can_manage_shifts` admin-role save test only. Every other shifts test lives in `shifts/tests.py`.
- `config/settings.py` (`INSTALLED_APPS` only) and `config/urls.py` (one include).
- `core/models.py` (the one flag), `core/migrations/0023_role_can_manage_shifts.py`, `core/forms.py` (`RoleForm` only), `templates/core/management/form_partial.html` (the Access checkbox and no preset entry).
- `templates/base.html` (the one sidebar link).
- `static/js/app-shell.js` (the three nav/ETag spots named above).
- `locale/ar/LC_MESSAGES/django.po` and the compiled `.mo` via `scripts/i18n.py`.
- `docs/reference/permissions-matrix.md` and `PROJECT_STANDARDS.md` (one row each).

Not allowed: behavior changes in Tickets, Dashboard, Knowledge Base, news, notifications, or push; edits to `modern.css`, `dark-mode.css`, `rtl.css`; changes to `TicketListPollSessionMiddleware` itself; new dependencies.

`shifts/migrations/0001_initial.py` is a normal Django migration. Tests will not execute it (`MIGRATION_MODULES`), which is the existing project rule.

## Ship path

1. One implementation PR by the dev agent, limited to the files above.
2. Code review by Greg (planner/reviewer).
3. Regression, performance, and permission tests on MySQL/MariaDB by the test agent, including the `DEBUG=0` static check and the manual dark-mode and RTL pass.
4. Merge only when Omar explicitly says yes.

No feature flag. The sidebar link is the rollout. Existing roles other than `admin` do not get the flag, so nobody becomes a manager by surprise. Branch users gain the Available now board. Support users gain My shifts (night hours and today’s day-shift check-in), Team rota, and that same board. None of that edits tickets or other apps.

## Open questions

None. The choices that were not spelled out in the first approval (Saturday week start, half-open intervals, one row per person per date, N limited to 12, rotation steps, auto-fill reusing that algorithm, 403 rather than a silent redirect, Available now showing every department to every logged-in viewer, templates in `templates/shifts/`, CSS in `static/css/shifts.css`, JS in `static/js/shifts.js`) are locked above. Worker night hours, the 7-day window, the 16-hour cap, the “Set by worker” audit split, and night hours meaning every effective minute of a night shift type are locked in decisions 12 and 18–22. Day-shift check-in, the 30-minute early window, no clear-audit columns, and coverage that ignores check-in are locked in decisions 8 and 23.
