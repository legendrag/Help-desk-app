# Project structure

Annotated layout of the mlamehticket repository and where day-to-day changes usually land.

**Audience:** Developers onboarding to the codebase or locating the right package for a change.

## Top-level layout

```text
app/
├── manage.py                 # Django entrypoint
├── requirements.txt          # Runtime deps
├── requirements-dev.txt      # polib, djlint, and related tooling
├── .env / .env.example       # Local/runtime configuration
├── PROJECT_STANDARDS.md      # Agent map: how the product works, stack, access, conventions
├── README.md
├── run-mlamehticket.ps1      # Local run helper
├── test-local.ps1            # Local test + i18n check helper
├── config/                   # Project package (settings, URLs, ASGI/WSGI)
├── accounts/                 # Users and auth
├── core/                     # Org entities, roles, email, maintenance, seeds
├── tickets/                  # Tickets, chat, dashboard, WS consumers
├── notifications/            # In-app + email + webpush integration
├── news/                     # Announcements
├── kb/                       # Knowledge base
├── scripts/                  # Non-app tooling (i18n)
├── installer/                # Packaging / Windows installer only
├── templates/                # Global + app templates (APP_DIRS also used)
├── static/                   # Source static assets (CSS/JS/images)
├── locale/                   # gettext catalogs (ar only today)
├── media/                    # Uploaded files (runtime)
├── staticfiles/              # Collected static (runtime / deploy)
└── docs/                     # Product and developer documentation
```

## `config/` — project package

| File | Purpose |
|---|---|
| `settings.py` | Apps, middleware, DB, Channels, i18n, WhiteNoise, webpush, test migration disable |
| `urls.py` | Root routes: apps, admin, i18n, webpush, `sw.js`, redirect `/` → tickets list |
| `asgi.py` | HTTP + WebSocket routing (`tickets` + `notifications`) |
| `wsgi.py` | WSGI fallback (prefer Daphne/ASGI in production) |

## Django apps

### `accounts/`

Custom `User` model, case-insensitive auth backend, login/logout/password-change views, user CRUD under Settings, `ForcePasswordChangeMiddleware`, logout-related webpush cleanup signals/tests.

### `core/`

Shared domain primitives:

- Models: `Branch`, `Department`, `Category` (ticket categories), `Role`, `EmailSetting`, `EmailTemplate`, abstract `TimeStampedModel`
- Management UI views for those entities
- Maintenance (export, media backup, cleanup)
- `core/seeds/` used by demo/seed management commands
- `core/middleware.py` — no-cache-after-logout

### `tickets/`

Primary product surface: list, detail/drawer, create/edit, status/pick/merge/transfer, dashboard + Excel export, settings hub shell.

| Module | Notes |
|---|---|
| `models.py` | Ticket, messages, status/merge history |
| `template_views.py` | Most HTTP endpoints |
| `access.py` | Org match + KB view bypass helpers |
| `consumers.py` / `routing.py` | Chat + list WebSockets |
| `realtime.py` | `group_send` helpers |
| `services.py` | Merge and related domain operations |
| `signals.py` | Broadcast + notification hooks on save/delete |
| `search.py` | List/search helpers |

### `notifications/`

| Module | Notes |
|---|---|
| `models.py` | `InAppNotification` |
| `services.py` | Orchestration: recipients, in-app create, WS broadcast, email enqueue, webpush |
| `email_queue.py` | In-process worker thread |
| `email_jobs.py` / `email_service.py` / `email_content.py` / `email_templates.py` | SMTP send path |
| `apps.py` | Runtime patches for `django-webpush` |
| `consumers.py` | Per-user notification socket |

### `news/`

`Announcement` model and CRUD views (list/create/update/delete). Branch-targeted or global visibility.

### `kb/`

Knowledge base: `Category` (**not** `core.Category`), `Article`, `ArticleAttachment`, browse/search, category management URLs.

### `scripts/`

`scripts/i18n.py` — extract / update / compile / check translation catalogs without GNU gettext binaries. Requires `polib` from `requirements-dev.txt`.

### `installer/`

Offline Windows packaging (Inno Setup): `build.ps1`, `fetch-payload.ps1`, `setup.iss`, `install.ps1` / `preupgrade.ps1` / `uninstall.ps1`, and `lib\` helpers. Payload binaries live in git-ignored `installer/payload/`. Not part of the Django runtime app graph.

## Templates and static

```text
templates/
├── base.html                 # Shell, language, Tom Select, WS hooks
├── sw.js                     # Service worker template
├── accounts/ … tickets/ …    # Per-app pages and partials
└── notifications/email/      # Email HTML shells

static/
├── css/                      # style.css, modern.css, dark-mode.css, rtl.css
├── js/                       # chat, notifications, charts, KB search, …
└── images/                   # Brand assets
```

`TEMPLATES["DIRS"]` points at project `templates/`; app-level templates are also discovered via `APP_DIRS`.

## Docs layout

```text
docs/
├── README.md                 # Doc index by audience
├── user-guide/               # End-user how-tos
├── admin-guide/              # In-app admin topics
├── operations/               # Install, deploy, backup, security
├── developer-guide/          # This guide
└── reference/                # Glossary / matrices (when present)
```

## Where to change what

| Goal | Start here |
|---|---|
| New ticket behavior / HTTP endpoint | `tickets/template_views.py`, `tickets/urls.py` |
| Org / role / email admin UI | `core/management_views.py`, `core/models.py` |
| Who gets notified | `notifications/services.py` |
| Live chat / list refresh | `tickets/consumers.py`, `tickets/realtime.py`, `static/js/` |
| Arabic strings | Templates / `_()` in Python, then `scripts/i18n.py` |
| CSS look and feel | `static/css/modern.css` (and related) — not Tailwind |
| Packaging installer | `installer/` only |

## Related docs

- [Architecture](architecture.md)
- [Data model](data-model.md)
- [Contributing](contributing.md)
