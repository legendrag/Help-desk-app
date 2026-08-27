# mlamehticket — how this project works

Persistent briefing for agents (and humans) changing this repo. It describes **current behavior**. If this file and the code disagree, **trust the code**, then update this file.

Deeper docs live under [`docs/`](docs/README.md). Do not duplicate them here.

---

## What this product is

mlamehticket is a **branch help-desk**. Branch staff (Needs Support) open tickets. Support agents pick, chat, transfer, merge, wait, close, and reopen them. Live updates use WebSockets. The UI is bilingual English / Arabic.

It is a **Django 6 monolith**: server-rendered HTML, HTMX partials, vanilla CSS/JS. There is no SPA frontend.

---

## Stack and non-goals

| Layer | What we use |
|---|---|
| Backend | Python 3.12+ · Django 6 · session auth |
| Frontend | Django templates · HTMX · vanilla CSS/JS |
| Selects / charts | **Tom Select** (CDN) · Chart.js on the dashboard |
| Realtime | Django Channels · Daphne · `InMemoryChannelLayer` |
| Email | In-process daemon thread (`notifications.email_queue`) |
| DB | SQLite (dev) · MySQL via PyMySQL (production) |
| Languages | `en` + `ar`; cookie `django_language`; **no `/ar/` URL prefixes** |
| Packaging | Windows Inno Setup installer under `installer/` |

**Do not add** React/Vue, Tailwind, Celery, Redis, or a second frontend build step unless the project explicitly changes architecture.

**Realtime limit:** `InMemoryChannelLayer` is process-local. Multiple Daphne workers will not share chat/list/notification events. Email is likewise in-process, not a broker.

---

## Where code lives

| Package | Role | Start here |
|---|---|---|
| `accounts/` | Custom user, login, force-password-change, user CRUD | `accounts/models.py`, `accounts/middleware.py` |
| `core/` | Branch, department, ticket category, role, email settings/templates, maintenance, seeds | `core/models.py`, `core/management_views.py` |
| `tickets/` | Lifecycle, chat, list, dashboard, merge/transfer, Settings Hub shell | `tickets/template_views.py`, `tickets/access.py`, `tickets/models.py` |
| `notifications/` | In-app, WebSockets, email queue, web push | `notifications/services.py`, `notifications/consumers.py` |
| `news/` | Announcements | `news/views.py` |
| `kb/` | Knowledge base articles (separate from ticket categories) | `kb/views.py`, `kb/models.py` |
| `config/` | Settings, URLs, ASGI/WSGI | `config/settings.py`, `config/asgi.py` |
| `templates/` | SSR HTML (plus app `templates/`) | `templates/base.html` |
| `static/` | CSS/JS/images | `static/css/`, `static/js/` |
| `scripts/i18n.py` | Extract / update / compile / check Arabic catalogs | `locale/ar/` |
| `installer/` | Offline Windows installer only | `installer/README.md` |

Ticket HTTP endpoints are mostly in `tickets/template_views.py`. New ticket **authorization** belongs in or next to `tickets/access.py`, not copied ad hoc into each view.

---

## Access: three layers

These are independent. Check all three.

1. **`user_type`** — `branch` (Needs Support, scoped by `user.branch`) or `support` (agent, scoped by `user.department`).
2. **`core.Role` flags** — ~31 booleans on `user.role`. Missing role ⇒ denied for gated actions. A role named `admin` (case-insensitive) **turns every flag on** at save. That is not the same as Django superuser.
3. **`is_superuser`** — bypasses role flags and sees all tickets.

Full flag list: [`docs/reference/permissions-matrix.md`](docs/reference/permissions-matrix.md). Tenancy rules: [`docs/developer-guide/permissions-and-scoping.md`](docs/developer-guide/permissions-and-scoping.md).

### Tenancy

| Who | Default ticket visibility |
|---|---|
| Branch user | `ticket.branch_id == user.branch_id` |
| Support user | `ticket.department_id == user.department_id` |
| Superuser | All tickets |

### Helpers in `tickets/access.py`

| Helper | Use for |
|---|---|
| `user_in_ticket_org` | Mutations, pick, reopen, **chat WebSocket**. Strict org match. **No KB bypass.** |
| `user_can_view_ticket` | HTTP detail/drawer **read**. Org match **or** KB bypass. |
| `user_can_pick_ticket` | Pick: org + unassigned + not merged + `can_pick_ticket`. |
| `user_can_reopen_ticket` | Reopen: org + same-dept support (or `can_update_closed_ticket` / superuser). |

**KB bypass (intentional, view-only):** if `can_access_kb` and the ticket has a **published** related KB article, HTTP can show the ticket across org boundaries. Chat WebSocket, pick, reopen, and other writes must **not** use this. Do not copy `user_can_view_ticket` onto mutating endpoints.

`ForcePasswordChangeMiddleware` redirects almost every request to password change when `user.requires_password_change` is true.

---

## Tickets

Core model: `tickets/models.py`. Number format: `{BRANCH_CODE}-{YYYYMMDD}-{SEQUENCE}` with `select_for_update`. Fields include title, description, branch, department, **ticket** category, priority, status, assignee, `client_name` / `client_phone`, merge pointer, pending transfer FKs.

**Statuses:** `open` · `in_progress` · `waiting_for_branch` (UI: Waiting) · `closed` · `merged`.

**Priorities:** `low` · `medium` · `high` · `urgent`. Category can supply a default priority.

**Time fields:** `picked_at`, `closed_at`, `total_pending_duration_seconds` (time spent Waiting), `last_status_change_at`. Detail page derives response / resolution / time-to-close from those.

**History:** every status/transfer/merge-style event writes `TicketStatusHistory` (`event_type` + optional `detail`).

### List and search

`TicketListView`, 25 per page, scoped querysets as above. HTMX can return `tickets/list_live_partial.html` for live refresh.

Search (`tickets/search.py`) is **AND across tokens**, not a single `icontains` on title/description. Tokens match ticket number, title, description, client name/phone (digits ignore separators), branch/department/category names, assignee and creator usernames. Ranking prefers exact/ID/title hits.

Filters: branch, status, assignee (including unassigned).

### Actions

| Action | Notes |
|---|---|
| **Pick** | Assigns current support user, typically `in_progress`, notifies, broadcasts. Org-scoped. |
| **Status** | Role `can_update_status`. Reopen uses `user_can_reopen_ticket` (not “any support, any ticket”). |
| **Edit** | `can_update_ticket`; HTMX modal partials. |
| **Transfer** | Assignee or superuser → another **same-department** agent. Pending `pending_transfer_to` / `_by` until accept / deny / cancel. Branch users do not transfer. |
| **Merge** | `can_update_status` or superuser. `tickets.services.merge_tickets`; secondary becomes `merged` with `merged_into`. HTMX search: min 2 chars, exclude already-merged. |

### Chat

Messages: `TicketMessage` — text, optional one attachment, `reply_to` threading, `is_system_message` (+ `message_ar` for system text). `clean()` **blocks non-system messages** on closed/merged tickets. Attachments: `validate_ticket_attachment` against `ALLOWED_ATTACHMENT_EXTENSIONS` and `MAX_ATTACHMENT_SIZE` (10 MiB; pdf/docx/xlsx/jpg/jpeg/png). Stored under `media/tickets/{ticket_id}/`.

**Composer UI (`can_chat`):** superuser, or branch user on a ticket in their branch, or support user who is the **assignee**. Closed/merged tickets should not accept new chat.

**WebSocket send** (`tickets/consumers.py`): authenticated; `user_in_ticket_org`; `can_send_message` (superuser always); support (non-superuser) only if **assigned**; reject closed/merged. Connect uses org match only (close `4401` unauthenticated, `4403` forbidden).

**HTTP `post_message` is looser** than the WebSocket path (branch = any ticket in branch; support = assignee **or** `can_send_message`, without `user_in_ticket_org`). **New chat/authz must follow `tickets.access` + the WebSocket rules**, not the older HTTP checks.

Live events on a ticket group `ticket_{id}`: `message_created` / `edited` / `deleted`, `ticket_status_changed`, `ticket_picked`, typing. List groups: `ticket_list`, `ticket_list_branch_{id}`, `ticket_list_department_{id}`.

Escape chat HTML (`escapeHtml` in `static/js/chat.js`; no `|safe` on message bodies).

---

## Other surfaces

| Surface | What it is | Gate |
|---|---|---|
| **Dashboard** | Volume, status bars, org breakdowns, Chart.js drill-down, Excel export, optional agent leaderboard | `can_access_dashboard`; leaderboard also `can_view_leaderboard`. Same tenancy as tickets. |
| **Notifications** | In-app bell (WS `user_{id}_notifications` + `/notifications/api/`), Web Push (`sw.js`), SMTP via in-process queue | Email toggles on active `EmailSetting` affect **email only**. Bilingual title/body fields exist on in-app rows. |
| **Announcements** | `news` app; optional branch targeting | Manage: `can_manage_news` |
| **Knowledge base** | `kb.Category` ≠ `core.Category`. Articles can link a related ticket. | View: `can_access_kb`. Manage: `can_manage_kb`. |
| **Settings Hub** | `/tickets/settings/` — HTMX tabs: branches, departments, categories, roles, users, email, conditional KB categories + maintenance | Open hub: `can_access_settings`. Each CRUD action has its own flag. |
| **PWA** | Manifest + service worker served from `core/pwa_views.py` (`Cache-Control: must-revalidate`, `Service-Worker-Allowed: /`) | Authenticated app shell |
| **Installer** | Inno Setup (`installer/setup.iss`, `build.ps1`), not a “PowerShell installer” as the product. Bundles Python/MySQL, Windows service, upgrades. | Ops docs |

Notification audiences (actor excluded): new ticket / pick / status → branch users of the ticket’s branch + support of its department + admins; replies → creator + assignee + admins (unassigned first message also pings branch/dept); transfer events → counterparty only. Message emails are often delayed ~120s. Details: [`docs/developer-guide/notifications-internals.md`](docs/developer-guide/notifications-internals.md).

---

## UI conventions

- **Templates + HTMX:** detect `HX-Request` and return `*_partial.html` / live list fragments. Use existing `HX-Trigger` names (`closeModal`, `refreshTickets`, `reloadPage`) rather than inventing a JSON API for the same UI.
- **CSS:** `static/css/modern.css` (tokens, glass/panels), `style.css` (structure), `rtl.css`, `dark-mode.css`. Extend tokens; do not add Tailwind. Prefer directional helpers over hard-coded left/right.
- **JS:** `static/js/chat.js`, `notifications.js`, and small page scripts. **Tom Select**, not Choices.js.
- **i18n:** wrap user-facing copy in `{% trans %}` / `{% blocktrans trimmed %}` / gettext. After string changes: `python scripts/i18n.py update` → translate → `compile` → `check --verbose`. See [`docs/developer-guide/i18n.md`](docs/developer-guide/i18n.md).
- **Tone:** professional, grounded hovers (no energetic scale/pop). Empty states stay muted and consistent.

---

## Agent do / don’t

**Do**

- Read `tickets/access.py` before adding ticket HTTP or WebSocket behavior.
- Scope querysets by branch/department unless the user is a superuser.
- Return HTMX partials when the request is `HX-Request`.
- Keep installer changes inside `installer/`.
- Add Django `TestCase` coverage for tenancy and permission changes (`python manage.py test`). Prefer extending `tickets.tests` (especially security/tenancy classes).
- Update the matching `docs/` page when user-visible behavior changes.

**Don’t**

- Widen KB bypass into pick, reopen, chat write, or other mutations.
- Assume Celery/Redis exist, or run multiple Daphne workers expecting shared Channels.
- Introduce React/Vue/Tailwind or Choices.js.
- Add `/ar/` URL prefixes; language is a cookie.
- Treat a role named `admin` as Django superuser (or the reverse).
- Copy the incomplete permission table from older versions of this file — use the [permissions matrix](docs/reference/permissions-matrix.md).
- Leave new English-only strings without a catalog update.

---

## Where to go next

| Need | Doc |
|---|---|
| Contributing conventions | [`docs/developer-guide/contributing.md`](docs/developer-guide/contributing.md) |
| Request flow, middleware, non-goals | [`docs/developer-guide/architecture.md`](docs/developer-guide/architecture.md) |
| Models | [`docs/developer-guide/data-model.md`](docs/developer-guide/data-model.md) |
| WebSocket events / close codes | [`docs/developer-guide/realtime.md`](docs/developer-guide/realtime.md) |
| URLs | [`docs/developer-guide/url-reference.md`](docs/developer-guide/url-reference.md) |
| Tests | [`docs/developer-guide/testing.md`](docs/developer-guide/testing.md) |
| End-user flows | [`docs/user-guide/`](docs/user-guide/getting-started.md) |
| Settings / roles | [`docs/admin-guide/settings-hub.md`](docs/admin-guide/settings-hub.md) |
