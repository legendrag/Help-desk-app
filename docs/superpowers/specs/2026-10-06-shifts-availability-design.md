# Shifts & availability

**Status:** Design approved by owner; spec awaiting owner review.

**Owner:** Omar (GitHub `legendrag`).

**Date:** 2026-10-06.

**Product:** mlamehticket, the Django help-desk. This spec adds a dated staff rota and a “who is on shift right now” board. It does not change tickets, chat, dashboard, knowledge base, news, or notifications.

## Goal

Support managers need a dated rota per department: who works which shift on which calendar day, including overnight shifts that start one evening and end the next morning. Branch staff need to see, right now, which support workers are on shift and when that shift ends. Support workers need a read-only view of their own upcoming shifts and their own department’s rota.

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
7. Branch users who are not managers can open only the Available now board. Support users who are not managers can open My shifts, Team rota (own department only), and the same Available now board. They cannot open manager URLs.
8. Available now shows the same payload to every viewer: per department, the names of people whose shift contains the current instant, and that shift’s end time. No start time, shift-type name, phone, email, hours, or any other field. No date query parameter changes the window.
9. Week grids start on Monday in `TIME_ZONE`. Arabic RTL mirrors layout; it does not move the week start to Saturday or Sunday.
10. Repeat-forward accepts N from 1 through 12 inclusive.
11. Copy, repeat, auto-fill, and the night-rotation apply never overwrite an existing assignment and never skip the overlap rule quietly. Conflicts are listed.
12. Night vs day hours means “before local midnight on the assignment date” vs “after that midnight”. It does not mean a second night-time clock (for example 22:00–06:00 is 2 day hours + 6 night hours).
13. `ShiftType.is_night` is computed, not typed: true exactly when `end_time < start_time`.
14. Shift-type names are unique per department, including archived rows. Archiving does not free the name.
15. Delete is not offered for shift types. Archive only. `on_delete=PROTECT` so a department, user, or shift type that still has rows cannot be deleted out from under the rota.
16. Times are the deployment `TIME_ZONE` only. Per-branch zones are out of scope. See Edge cases for the DST assumption.
17. Polling exists only on Available now, every 20 seconds, and only while the browser tab is visible. No WebSockets, no Channels consumer, no cache framework, no Celery.

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
| `start_time_override` | `TimeField(null=True, blank=True)` | Both overrides or neither. |
| `end_time_override` | `TimeField(null=True, blank=True)` | If set, must differ from the start override. |
| `created_at` / `updated_at` | `TimeStampedModel` | |

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

`effective_is_night(assignment)` is `end_t < start_t`. A day type with a crossing override is a night for that date. A night type with an override that does not cross is not.

Equal start and end is a validation error (`"Start and end must differ."`), on the type and on the override pair. A single override without the other is `"Enter both start and end, or leave both blank."`

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

`clean()` / the cell form, and again inside `transaction.atomic` before every bulk write:

1. Reject a second row for the same `(user, date)` with `"This person already has a shift on this date."`
2. Load that user’s assignments on `date - 1 day`, `date`, and `date + 1 day` (exclude the row being saved).
3. If the new half-open interval intersects any of those intervals, reject with `"This shift overlaps %(name)s on %(date)s (%(start)s–%(end)s)."` using the other shift’s type name and local times.

Example: Monday 22:00–06:00 and Tuesday 01:00–09:00 overlap. Monday 22:00–06:00 and Tuesday 06:00–14:00 do not. Monday 09:00–17:00 and Monday 18:00–22:00 cannot both exist, because the unique constraint is one row per date, not because the clock intervals meet.

### Archived types and department changes

- Historic cells (`date < today`) render the type name and colour even when `archived=True`.
- Today and future cells that already point at an archived type keep showing it, with an “Archived” marker. The picker does not offer it. Copy and repeat skip archived source types.
- Today and future cells where the user is no longer an active support user of that department show a “Not in this department” badge (or “Inactive” when the department still matches but `status` is not active). The row stays. It still blocks overlap. It still counts for hours and coverage. It still appears on Available now while the interval contains now. The rotation suggester will not pick that user as a new candidate. Nothing is deleted automatically.

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

| Viewer | Shift types, rota edits, copy, repeat, auto-fill, calculator | My shifts | Team rota | Available now |
|---|---|---|---|---|
| Anonymous | login redirect | login redirect | login redirect | login redirect |
| Superuser | allow, all departments | allow (own rows; may be empty) | allow, any department | allow |
| Role `can_manage_shifts` (any `user_type`) | allow, all departments | allow | allow, any department | allow |
| Support, flag off | 403 | own upcoming only | own `user.department_id` only, read-only | allow |
| Branch, flag off | 403 | 403 | 403 | allow |
| Support with no department, flag off | 403 | own upcoming only | empty state, no department picker | allow |

Support Team rota ignores a requested `department` that is not theirs and returns 403 if the query string tries to switch department. Managers may pass any department id.

Available now lists **every** department’s current names to every logged-in viewer, including branch users and support users. That is the board. It is not scoped to the viewer’s department. It still must not include future days or hours.

## URLs, views, templates

Include in `config/urls.py` next to the other apps:

```python
path("shifts/", include("shifts.urls")),
```

`INSTALLED_APPS` gains `"shifts"` after `"webpush"`.

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
| `shifts_team` | GET | `/shifts/team/` | Read-only team rota. |

Default redirect from `shifts_home`:

- manager → `shifts_rota`
- support, not manager → `shifts_mine`
- branch, not manager → `shifts_available`

Query strings:

- Rota and team: `view=week|month` and `start=YYYY-MM-DD`. `start` is normalized to the Monday of that week, or to the first of the month when `view=month`. Missing `start` means the week (or month) that contains `timezone.localdate()`.
- Rota also takes `department=<id>`. Missing department means the first department by name. A bad id is 404.
- Team rota has no department parameter for non-managers. Managers opening Team rota may pass `department`.
- Calculator hours and coverage: `department`, `view`, `start`, same normalization.
- Rotation: POST body `department`, `start`, `end` (inclusive local dates), `shift_type`, `users` (one or more ids), `action=preview|apply`.
- Length: `start` and `end` as `HH:MM` times, no date.
- Cell: POST `user`, `date`, `department`, optional `shift_type` (empty means clear), optional `start_time_override`, `end_time_override`.

### Templates

Under `shifts/templates/shifts/`:

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
| `mine.html` | Read-only list. |
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

Toolbar (managers, week view and month view):

- Department `<select>` of all departments, ordered by name.
- Previous / next, and a date input. Week view labels the Monday–Sunday range. Month view shows that month.
- A week/month toggle. Switching view keeps the same anchor date.
- **Copy last week** (week view only; hidden in month view).
- **Repeat this week forward** with a number input N (week view only).
- **Auto-fill nights** (both views; the range is the visible dates).

Grid:

- Rows: active support users in the selected department, plus anyone who already has an assignment on a visible date (so a person who changed department still appears on historic and flagged future cells). Order by first name, then username. One query.
- Columns: each date in the week or month. Header is the translated short weekday and the day number.
- Empty cell: a button the manager can activate. Read-only grids (team rota) are not buttons.
- Filled cell: colour as `background-color` from `ShiftType.colour`, type name as text, and times only when an override is set (otherwise the type’s times are in the accessible name, not a second line). Night cells (`effective_is_night`) also get class `shifts-cell--night` and a visible “Night” label. Colour is not the only night signal.
- Badges: “Archived”, “Not in this department”, “Inactive”, as defined above.
- Click (managers) opens the cell modal: shift type `<select>` of non-archived types for that department, optional override times, Save, and Clear when the cell is filled.

Queries for one grid (no per-cell queries):

1. Assignments with `date__gte=first_visible_date - 1 day` and `date__lte=last_visible_date`, `shift_type__department` = selected, `select_related("user", "shift_type")`, `only()` the columns the template prints. The extra day is for overlap display and for Monday early coverage; it is not an extra column.
2. Users as described, `only("id", "username", "first_name", "last_name", "department_id", "user_type", "status")`.

ETag for `shifts_rota_grid` and the shell pane: `etag_digest` of language, department id, view, start, assignment count, max `updated_at` of those assignments, and max `updated_at` of the department’s shift types. Use `htmx_revalidation_match` / `htmx_not_modified` / `apply_read_etag`. Do not set `ticket_list_304_defer_session_save` on rota GETs; they are not a 20s poll.

### Copy, repeat, auto-fill

All three are manager POSTs, CSRF-protected, `transaction.atomic`, department-scoped.

**Copy last week.** For each date D in the displayed Monday–Sunday, look at D−7 days. If that source row’s type is archived, skip it (“archived shift type”). If the target user already has a row on D, skip it (“already assigned”). If the copied interval would overlap a neighbor, skip it (“overlaps …”). Otherwise create the same user, type, and overrides on D. Source Sunday’s overnight tail is not copied onto target Monday; Monday’s cell comes only from the previous Monday. The overlap check still sees that tail.

**Repeat this week forward.** N is an integer 1–12. Anything else is a form error `"Enter a number of weeks from 1 to 12."` For k = 1..N, copy each displayed-week assignment onto `date + 7*k days` with the same skip rules, including rows created earlier in this same transaction. Process dates in order so a copied Sunday night is visible when the next Monday is checked.

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

Read-only. Rows are the logged-in user’s assignments with `date__gte=local today`, ordered by date, plus a banner when yesterday’s assignment still contains `timezone.now()`: `"You are on shift until %(end)s."` The list shows date, type name, colour, effective times, and the Night label. No other people’s rows. No edit controls. Empty: `"You have no upcoming shifts."`

### Team rota

Same grid component as the manager rota, `readonly=True`: no toolbar actions, no cell modal, no type management. Non-managers are pinned to `request.user.department`. If that FK is null, render `"You are not assigned to a department."` and no grid. Managers may pick a department.

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

Who is on shift: load assignments with `date__in=[local_yesterday, local_today]` (Python dates, then a `DateField` lookup — not `__date` on a datetime). `select_related("user", "shift_type", "shift_type__department")`. In Python, keep rows whose interval contains `timezone.now()`, and group by `shift_type.department`. Include yesterday’s overnight shift. Do not include tomorrow. A shift that ends at the current minute is already over.

`shifts/static/shifts/shifts.js` (loaded only from the shifts shell via `{% block extra_js %}`):

- On `htmx:configRequest`, if the element id is `shifts-available-now` and it has `data-etag`, set `If-None-Match`.
- On `htmx:beforeSwap`, if the target id is `shifts-available-now` and the status is 304, set `shouldSwap = false` and `isError = false` (same idea as the `#tickets-live` handler, but in this file).
- On `visibilitychange`, when `document.hidden` becomes false, trigger one refresh of `#shifts-available-now` so the board does not sit stale for up to 20 seconds. That is still a single bounded request, not a second timer.

The view builds the ETag with `etag_digest` of the language and, per department id, the sorted `(user_id, end_isoformat)` pairs. Same helpers as the ticket list: `htmx_revalidation_match`, `htmx_not_modified`, `apply_read_etag`. On the 304 path only, set `request.ticket_list_304_defer_session_save = True` so idle polls reuse `TicketListPollSessionMiddleware` instead of rewriting the session every 20 seconds. Do not modify `core/session_middleware.py`. The flag name is historical; the middleware already honors it for any view that sets it.

Ignore extra query parameters. The HTML must not contain start times, type names, colours, phone numbers, or hour totals. Tests assert that.

## Calculator

Managers only. One page, four tools, each posting or getting its own partial so a long heatmap does not redo the others. All four call the same interval helpers. Math is in Python (`shifts/services.py`), not in the browser, so tests can lock it.

### 1. Hours per person

Inputs: department, week or month (same `view` and `start` as the rota).

For every assignment of that department whose interval overlaps `[range_start, range_end)` — `range_end` is the start of the day after the last visible date — clip the interval to that window. Split the clipped part at local midnights.

- **Day hours:** minutes whose local calendar date equals the assignment’s `date`.
- **Night hours:** the rest (the part after midnight, including minutes that land on the next date).
- **Total:** day + night.

A Sunday 22:00–06:00 shift clipped to a Monday–Sunday range that starts that next Monday contributes 6 night hours and 0 day hours. The same shift inside a range that includes that Sunday contributes 2 day hours (22:00–00:00) and 6 night hours. A 09:00–17:00 shift is 8 day hours and 0 night hours. A 00:00–08:00 shift does not cross midnight, so it is 8 day hours and 0 night hours.

Show one row per person who has a non-zero clipped total, display name, day, night, and total, as hours and minutes (compute in integer minutes; do not use floats). Omit people with no assignments in range.

### 2. Night-rotation suggester

Inputs: department, inclusive start date, inclusive end date, one non-archived night `ShiftType` in that department, and a non-empty subset of that department’s active support users.

Constant `NIGHT_ROTATION_LOOKBACK_DAYS = 14` in `shifts/services.py`.

Algorithm, deterministic:

1. `dates` = each local date from start through end inclusive.
2. Lookback night count for each included person = how many of their existing assignments in `[start - 14 days, start)` have `effective_is_night`. Also record the latest such date, or none.
3. `proposed` starts empty. Walk `dates` in order.
4. A person is a candidate on D when all of these hold:
   - they have no existing assignment on D
   - they have no proposed assignment on D
   - the target type’s interval on D does not intersect their existing or proposed intervals (check D−1, D, and D+1)
   - they are still in the included set
5. Prefer candidates who were **not** on a night (existing or already proposed) on D−1. If that set is empty, allow a back-to-back candidate and mark the proposal `back_to_back=True`. If that set is also empty, record a gap for D and continue.
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

### 4. Coverage gaps

Inputs: department, week or month.

Columns are the visible dates. Rows are local hours 00 through 23. A person covers hour H on date D when their interval overlaps `[D H:00, D H+1:00)`. A shift ending at 06:00 does not cover the 06:00 hour. Yesterday’s overnight (assignment date = first column − 1 day) covers the early hours of the first column. The last column’s overnight hours that fall on the next calendar date are not extra columns; they simply do not appear.

Cell text is the count. Count 0 uses class `shifts-gap` (highlighted) and the text `0`, so colour is not the only signal. The heatmap query is the same assignment fetch as the grid, including the day before the range.

## Performance

- In-shell navigation only, as specified above. No full page reload is required for tabs, cell saves, or the board poll.
- ETag/304 via `core/http_cache.py` on the rota grid (and the shifts shell pane) and on the Available now board. Digest the values listed above; do not hash the whole HTML by rendering twice unless that is cheaper, which it is not.
- `select_related` / `only` as specified. The grid and the board must not query inside a row loop. Tests can assert query counts with `assertNumQueries` on the grid and board views (a small fixed budget, not “whatever the template does”).
- The only `every` poll in the app’s new templates is the 20s Available now trigger, gated on `!document.hidden`, with `data-no-progress`.
- No new WebSocket, no `CHANNEL_LAYERS` change, no Django cache, no Redis.
- Available now 304 sets the existing session-defer flag. Rota 304 does not.

## UI, responsive, accessibility, RTL

Match existing components. Do not restyle Tickets, Dashboard, or Settings.

Reuse classes from `static/css/modern.css`: `.panel`, `.btn`, `.btn.primary`, `.btn.secondary`, `.btn.danger`, `.table-wrap`, `.notice`, `.notice-error`, `.badge`, `.settings-tabs`, `.settings-tab`, `.form-group`, `.form-actions`, modal classes already on `#modal-container`.

New rules live only in `shifts/static/shifts/shifts.css`, loaded from the shifts shell. Scope under `#shifts-shell-pane`. Use the existing variables (`--panel-bg`, `--text-main`, `--text-muted`, `--border`, `--bg`, `--warning`, `--danger`) so `[data-theme="dark"]` from `dark-mode.css` applies without editing that file. Do not edit `static/css/modern.css`, `dark-mode.css`, `rtl.css`, or `style.css`.

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
- Do not force `direction: ltr` on the grid. `html[dir=rtl]` from `base.html` (and `rtl.css`) mirrors the table. Monday stays the first date in DOM order; in Arabic it appears on the right.
- Every user-visible string is `{% trans %}` or `{% blocktrans trimmed %}`. Run `python scripts/i18n.py update` and `compile` in the implementation PR so `locale/ar/LC_MESSAGES/django.po` and `.mo` contain the new msgids. English remains the source language.

Times on the rota, the board, and My shifts render with the `H:i` format (24-hour). Dates use Django’s localized date filters.

## Edge cases

| Case | Behavior |
|---|---|
| Midnight-crossing shift | Stored on the start date. Counts as on shift until `end_dt`. Available now checks yesterday and today. |
| Touching endpoints | `[22:00, 06:00)` and `[06:00, 14:00)` do not overlap. |
| Two shifts the same calendar day | Blocked by the unique constraint even if the clocks would not overlap. |
| Overlap from yesterday’s night into today | Blocked with the overlap message. |
| Archived type on a past date | Still shown, name and colour. |
| Archived type on a future date that was assigned before archive | Still shown, “Archived” badge. Not offered for new cells. |
| User changes department | Past cells unchanged and not badged. Today and future cells badged “Not in this department”, kept, still blocking overlap, still eligible for Available now until they end. |
| User deactivated | Same badge rules, worded “Inactive” when the department still matches. They cannot be newly assigned. |
| Department with nobody on shift | That card reads “Nobody on shift now”. Other departments still render. |
| Support user with no department | My shifts still works. Team rota shows the empty-department sentence. |
| Copy onto a filled cell | Skip, listed, existing row unchanged. |
| Repeat N outside 1–12 | Form error, no writes. |
| Rotation vs an existing cell | Preview shows a gap or the apply step lists a skip. The existing assignment is not replaced. |
| All candidates would work back-to-back | Allow it, mark those proposals, do not fail the whole range. |
| DST | Assumption: this deployment uses one `TIME_ZONE` and does not rely on per-branch zones. Default is `UTC`, which has no DST. If `TIME_ZONE` is a zone with DST, intervals follow that zone’s `zoneinfo` rules with no extra compensation (a crossing shift can be 7 or 9 clock hours on the transition). A start or end that lands in a missing local hour raises `"That time does not exist on this date."` Ambiguous times use Django’s default `make_aware` (first occurrence). The length tool has no date, so it is pure clock arithmetic and ignores DST. |
| MySQL timezone tables | Filter `ShiftAssignment.date` with `date__gte`, `date__lte`, and `date__in` only. Build “today” and “yesterday” in Python with `timezone.localdate()`. Do not use `__date`, `TruncDate`, or `CONVERT_TZ` lookups on datetimes. |
| Equal start and end | Validation error, nothing saved. |
| Colour not a 6-digit hex | Validation error. |
| Manager is a branch user | Treated as a manager on every shifts endpoint. |
| Admin role | Migration backfill plus `Role.save()` keep `can_manage_shifts` true. Other existing roles stay false. |

## Testing

New tests in `shifts/tests.py` using Django `TestCase` and the test client. Build users with explicit `user_type`, `department` or `branch`, `status`, and a `Role`. Migrations do not run under `manage.py test`; cover `Role.save()` and model `clean()` directly. The `RunPython` admin backfill is checked by reading the migration, not by the test runner.

Unit and view tests:

- Available now includes a Monday 22:00–06:00 assignment when `timezone.now()` is Tuesday 05:00, and excludes it at Tuesday 06:00. Freeze time with `django.utils.timezone` override.
- Available now ignores a shift that starts later today.
- A department with no covering assignment renders “Nobody on shift now”.
- Overlap: adjacent night vs early morning rejected; touching endpoints allowed; second row the same date rejected.
- Department and user-type checks: branch user, support user of another department, and inactive support user cannot be assigned on a future date. A past assignment remains after the user’s department changes, and the future one is flagged in the rota HTML.
- Archived type still rendered on a past date; POST of that type onto a future empty cell fails.
- Hours: 22:00–06:00 inside a range that contains both dates is 2 day hours and 6 night hours (120 and 360 minutes). Clipped to the following day only, 6 night hours. 09:00–17:00 is 8 day hours.
- Length tool: 22:00–06:00 → 8 hours total, 6 after midnight. 09:00–12:30 → 3 hours 30 minutes, 0 after midnight. Equal times → error.
- Rotation fairness cases listed in tool 2, including “does not change an existing assignment”.
- Coverage: the 05:00 hour on Tuesday is covered by Monday’s night shift; the 06:00 hour is not; an hour with no row has text `0` and class `shifts-gap`.
- Permissions: for every named URL, assert status for anonymous (redirect to login), branch non-manager, support non-manager, support non-manager of another department (team rota and rota GET with `department=`), manager (`can_manage_shifts` and not superuser), and superuser. Branch responses for rota, types, calculator, mine, and team are 403 and the body does not contain another day’s schedule or an hour total. Support POST to cell, copy, repeat, auto-fill, type archive, and rotation apply is 403.
- Available now HTML for a branch user contains the on-shift display name and end time and does not contain the shift type name or the start time.
- ETag: GET the board with `HTTP_HX_REQUEST=true`, then repeat with `HTTP_IF_NONE_MATCH` equal to the `ETag` header, and assert 304 and an empty body. A changed assignment returns 200. A history-restore header (`HTTP_HX_HISTORY_RESTORE_REQUEST=true`) returns 200, matching `htmx_revalidation_match`.
- Admin role: `Role(name="admin").save()` sets `can_manage_shifts` True. A role named `Support` saves the flag as given.
- Grid query count stays within the budget asserted in the test (no N+1).

MySQL/MariaDB (test agent, not the unit-test default SQLite):

- Run the shifts tests and the existing suite against `DB_ENGINE=mysql` with `USE_TZ=True` and without loading MySQL timezone tables. Assignment filters on `date` must still return the overnight row. This is the regression that `__date` on a `DateTimeField` would fail.

`DEBUG=0` static check:

- `collectstatic` with `CompressedManifestStaticFilesStorage` succeeds, and the shifts shell’s `{% static 'shifts/shifts.css' %}` and `{% static 'shifts/shifts.js' %}` resolve in the manifest. App static is picked up by the app directories finder; do not add a new `STATICFILES_DIRS` entry.

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

- New tree `shifts/` (`models.py`, `services.py`, `access.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, `apps.py`, `tests.py`, `migrations/0001_initial.py` depending on `core.0023` and `accounts.0008_alter_requires_password_change_verbose`, templates, static).
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

No feature flag. The sidebar link is the rollout. Existing roles other than `admin` do not get the flag, so nobody becomes a manager by surprise. Branch and support users gain read-only screens the day the PR merges.

## Open questions

None. The choices that were not spelled out in the approval (Monday week start, half-open intervals, one row per person per date, N limited to 12, rotation steps, auto-fill reusing that algorithm, 403 rather than a silent redirect, Available now showing every department to every logged-in viewer, CSS kept inside the new app) are locked above.
