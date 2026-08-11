# mlamehticket

mlamehticket is a modern help-desk and ticket management platform built with **Django**, **HTMX**, and **vanilla JavaScript**. Branch staff open tickets; support agents pick, chat, transfer, merge, and close them — with real-time updates over WebSockets.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12+ · Django 6 (monolithic SSR) |
| Frontend | HTML5 · vanilla CSS · vanilla JS · HTMX |
| Real-time | Django Channels · Daphne (ASGI) · WebSockets |
| Database | SQLite (development) · MySQL via PyMySQL (production) |
| Auth | Django session authentication |
| Notifications | In-app · Web Push · SMTP email (in-process queue) |
| Languages | English · Arabic (cookie-based; no URL prefixes) |

There is **no** Celery, Redis, or Node/Tailwind build step.

## Key features

- Ticket lifecycle with pick, waiting, close, reopen, transfer, and merge
- Real-time chat and live ticket-list updates
- Multi-channel notifications (in-app bell, browser push, email)
- Role-based permissions (~31 granular flags) plus branch/support user types
- Analytics dashboard with Excel export
- Knowledge base and branch-targeted announcements
- Bilingual UI (English / Arabic) with RTL support
- Windows installer (Inno Setup) for offline client deployments — bundles Python/MySQL, runs as a Windows service, supports in-place upgrades

## Quick start

### Prerequisites

- Python 3.12+
- Virtual environment recommended (`.venv`)

### Setup and run

```powershell
# 1. Create and activate virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
Copy-Item .env.example .env

# 4. Migrate database
python manage.py migrate

# 5. Start the development server
python manage.py runserver
```

Or use the all-in-one launcher:

```powershell
.\test-local.ps1 -InstallDeps
```

### Initial access

- **URL:** http://localhost:8000
- **Bootstrap admin:** set `DEFAULT_SUPERADMIN_PASSWORD` in `.env` to a strong value before `migrate`. Auto-create is skipped if the password is empty or weak (`admin`, `password`, `changeme`, `12345678`). New bootstrap admins must change their password on first login.

For MySQL production setup, Daphne, and the Windows installer, see the [operations docs](docs/operations/installation.md).

## Documentation

Full English documentation lives in [`docs/`](docs/README.md):

| Audience | Start here |
|---|---|
| Branch staff & support agents | [User guide](docs/user-guide/getting-started.md) |
| In-app administrators | [Admin guide](docs/admin-guide/settings-hub.md) |
| Operators / deployers | [Installation](docs/operations/installation.md) · [Configuration](docs/operations/configuration.md) · [Deployment](docs/operations/deployment.md) |
| Developers | [Architecture](docs/developer-guide/architecture.md) · [Data model](docs/developer-guide/data-model.md) |
| Quick lookups | [Permissions matrix](docs/reference/permissions-matrix.md) · [Management commands](docs/reference/management-commands.md) · [Glossary](docs/reference/glossary.md) |

Common shortcuts:

- [Backup & restore](docs/operations/backup-restore.md)
- [Gmail app password (SMTP)](docs/admin-guide/gmail-app-password.md)
- [i18n workflow](docs/developer-guide/i18n.md)
- [Testing](docs/developer-guide/testing.md)
- [Troubleshooting](docs/operations/troubleshooting.md)

## Project layout

```
accounts/          User model, login, password change, user CRUD
core/              Branches, departments, categories, roles, email settings, maintenance, seeds
tickets/           Ticket lifecycle, chat, dashboard, settings hub
notifications/     In-app notifications, WebSockets, email queue, web push
news/              Announcements
kb/                Knowledge base articles and categories
config/            Django settings, root URLs, ASGI/WSGI
templates/         Server-rendered HTML
static/            CSS and JavaScript (chat.js, notifications.js, …)
scripts/           Pure-Python i18n tooling (scripts/i18n.py)
installer/         Windows offline installer (Inno Setup + WinSW service)
locale/            Arabic gettext catalogs
docs/              English documentation
```

## Testing, translations, and backups

```powershell
# Unit tests (Django TestCase)
python manage.py test

# Translations (requires: pip install -r requirements-dev.txt)
python scripts/i18n.py update
python scripts/i18n.py compile
python scripts/i18n.py check --verbose

# Database backup
python manage.py backup_db
```

See [Testing](docs/developer-guide/testing.md), [i18n](docs/developer-guide/i18n.md), and [Backup & restore](docs/operations/backup-restore.md) for full details.

## Production notes

- Set `DEBUG=0`, a strong `SECRET_KEY`, and non-wildcard `ALLOWED_HOSTS`.
- Use `DB_ENGINE=mysql` with a `utf8mb4` database.
- Run Daphne (not `runserver`) so WebSockets work — `.\run-mlamehticket.ps1`.
- Configure SMTP in **Settings Hub → Email Settings** (database), not in `.env`.
- Set `SITE_URL` so notification emails contain absolute links.

See [Deployment](docs/operations/deployment.md) and [Security hardening](docs/operations/security-hardening.md).
