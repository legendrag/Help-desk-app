# Configuration

Reference for environment variables and runtime settings used by mlamehticket.

**Audience:** Operators configuring `.env` and understanding which settings live in the database instead.

---

## How configuration is loaded

- Django loads `config/settings.py`, which reads **`BASE_DIR/.env`** via `python-dotenv`.
- Copy `.env.example` to `.env` and edit values for your environment.
- **SMTP is not configured in `.env`.** Outbound email uses the active **`EmailSetting`** row in the database (Settings → Email in the UI).
- Some knobs below appear only in `settings.py` defaults (not listed in `.env.example`); you can still set them in `.env` and they will be picked up.

Related: [Installation](installation.md) · [Deployment](deployment.md) · [Security hardening](security-hardening.md)

---

## Complete environment variable reference

| Variable | Description | Default | In `.env.example`? |
|----------|-------------|---------|--------------------|
| `DEBUG` | `"1"` enables debug mode; any other value is treated as false. Must be `0` in production. | `1` | Yes |
| `SECRET_KEY` | Django secret key for signing sessions and tokens. Use a long random string in production. | `change-this-to-a-very-long-random-secret-key` (settings fallback) / example uses `change-me-with-a-long-random-string` | Yes |
| `ALLOWED_HOSTS` | Comma-separated hostnames/IPs Django will accept. `*` is convenient for local only. | `*` | Yes |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins (scheme + host, e.g. `https://helpdesk.example.com`) trusted for CSRF. Required when browsers post from a named origin in production. | empty | Settings-only (not in `.env.example`) |
| `SITE_URL` | Public base URL of the app **without a trailing slash**. Used to build absolute links in notification emails. | empty string (settings); example sets `http://localhost:8000` | Yes |
| `DB_ENGINE` | Database backend: `sqlite` or `mysql`. | `sqlite` | Yes |
| `DB_NAME` | Database name (MySQL) or unused for default SQLite file naming beyond engine choice. | `mlamehticket` | Yes |
| `DB_USER` | MySQL username. | `root` | Yes |
| `DB_PASSWORD` | MySQL password. | empty | Yes |
| `DB_HOST` | MySQL host. | `localhost` | Yes |
| `DB_PORT` | MySQL port. | `3306` | Yes |
| `DB_CONN_MAX_AGE` | Persistent DB connection lifetime in seconds (MySQL). | `600` | Settings-only |
| `TIME_ZONE` | Django time zone name. | `UTC` | Settings-only |
| `DEFAULT_SUPERADMIN_USERNAME` | Username created on migrate when bootstrap password is strong. | `admin` | Yes |
| `DEFAULT_SUPERADMIN_EMAIL` | Email for the bootstrap superuser. | `admin@mlamehticket.local` | Yes |
| `DEFAULT_SUPERADMIN_PASSWORD` | Password for bootstrap superuser. Empty or weak values skip creation. Required and must be strong when `DEBUG=0`. | empty | Yes |
| `BACKUP_DIR` | Default directory for `backup_db` (must stay under project root). | `./backups` | Yes |
| `BACKUP_KEEP` | How many recent DB backups to retain. | `7` | Yes |
| `LOG_LEVEL` | Root / Django log level (`DEBUG`, `INFO`, `WARNING`, …). | `INFO` | Yes (commented) |
| `LOG_TO_FILE` | `"1"` writes daily-rotated `{BASE_DIR}/logs/app.log` (30 days) and drops the console handler to `WARNING`. Windows service sets this. | `0` | Yes (commented) |
| `VAPID_PUBLIC_KEY` | Web Push VAPID public key. Optional; generated/derived if blank. | empty (auto) | Yes (commented) |
| `VAPID_PRIVATE_KEY` | Path or material for VAPID private key. If unset, defaults to `private_key.pem` under the project root (auto-generated if missing). | empty → `private_key.pem` | Yes (commented) |
| `VAPID_ADMIN_EMAIL` | Contact email embedded in VAPID / webpush settings. | `admin@mlamehticket.com` (settings); example comments `admin@mlamehticket.local` | Yes (commented) |
| `SESSION_COOKIE_AGE` | Session lifetime in seconds. Sliding expiry is enabled (`SESSION_SAVE_EVERY_REQUEST`). | `259200` (3 days) | Settings-only |
| `TICKET_UNPICKED_SYSTEM_MESSAGE` | System chat line shown on unpicked tickets. | `Someone will help you soon.` | Settings-only |

“Settings-only” means the variable is read in `config/settings.py` but is not pre-listed in `.env.example`. You may still add it to `.env`.

---

## `SITE_URL` (important for email)

Notification emails include links to tickets and other pages. Those links are absolute only when `SITE_URL` is set correctly.

```env
# Good
SITE_URL=http://localhost:8000
SITE_URL=http://192.168.1.10:8000
SITE_URL=https://helpdesk.example.com

# Bad — trailing slash is stripped, but prefer none
SITE_URL=https://helpdesk.example.com/

# Bad — empty or wrong host → mail clients get relative paths like /tickets/1/
SITE_URL=
```

Without a usable `SITE_URL`, email clients often cannot open ticket links. Always set this to the URL users actually type in the browser (including LAN IP when that is how staff reach the server).

---

## Database engine notes

### SQLite (`DB_ENGINE=sqlite`)

- Default for `test-local.ps1` and local development.
- Database file: `db.sqlite3` in the project root.
- MySQL-specific vars are ignored for the connection.

### MySQL (`DB_ENGINE=mysql`)

- Required for the Windows installer post-setup (`install.ps1` forces `DB_ENGINE=mysql`).
- Create the schema with **utf8mb4** before migrate — see [Deployment](deployment.md).
- Connection uses PyMySQL; `DB_CONN_MAX_AGE` defaults to **600** seconds.

Example production fragment:

```env
DB_ENGINE=mysql
DB_NAME=mlamehticket
DB_USER=mlamehticket_user
DB_PASSWORD=strong-db-password
DB_HOST=localhost
DB_PORT=3306
DB_CONN_MAX_AGE=600
```

---

## Bootstrap superadmin password rules

Weak passwords (creation skipped; and when `DEBUG=0`, startup fails):

- `""` (empty)
- `admin`
- `password`
- `changeme`
- `12345678`

There is no `bootstrap_superadmin` command. Set a strong `DEFAULT_SUPERADMIN_PASSWORD`, then run `migrate`. New admins get `requires_password_change=True`. Details: [Installation](installation.md).

---

## SMTP is not in `.env`

Do **not** put SMTP host, port, username, or password in `.env`. Configure them in the app:

1. Sign in as an admin with email-settings permission.
2. Open **Settings → Email**.
3. Create or edit an **`EmailSetting`** (host, port, TLS, credentials, from-address, event toggles).
4. Use a test send if available.

For Gmail accounts that require app passwords, see [Gmail app password](../admin-guide/gmail-app-password.md).

Email event flags on `EmailSetting` gate **email only**; they do not turn off in-app or Web Push notifications.

---

## Web Push (VAPID)

If `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` are blank, the app can generate and persist keys (typically `private_key.pem` / `public_key.pem` in the project root). Treat `private_key.pem` like a secret; back it up with `.env` so push subscriptions keep working after rebuilds. See [Security hardening](security-hardening.md) and [Troubleshooting](troubleshooting.md).

---

## Sessions

```env
SESSION_COOKIE_AGE=259200
```

Default is **3 days**. Sessions are refreshed on each request (`SESSION_SAVE_EVERY_REQUEST = True`) and do not expire solely because the browser closed (`SESSION_EXPIRE_AT_BROWSER_CLOSE = False`).

---

## Backups

```env
BACKUP_DIR=./backups
BACKUP_KEEP=7
```

Used by `python manage.py backup_db`. The directory must remain inside the project root. See [Backup and restore](backup-restore.md).

---

## Attachment limits (code settings, not env)

These are fixed in `settings.py` (not overridable via `.env` today):

| Setting | Value |
|---------|--------|
| `MAX_ATTACHMENT_SIZE` | 10 MiB (`10 * 1024 * 1024`) |
| `ALLOWED_ATTACHMENT_EXTENSIONS` | `.pdf`, `.docx`, `.xlsx`, `.jpg`, `.jpeg`, `.png` |

---

## Channel layer

Channels uses **`InMemoryChannelLayer`**. There is no Redis/Celery configuration in `.env`. Real-time events stay in-process; multi-worker / multi-process deploys need a shared channel layer backend. See [Security hardening](security-hardening.md) and [Deployment](deployment.md).

---

## Minimal examples

### Local development

```env
DEBUG=1
SECRET_KEY=dev-only-change-me
ALLOWED_HOSTS=*
SITE_URL=http://localhost:8000
DB_ENGINE=sqlite
DEFAULT_SUPERADMIN_PASSWORD=
BACKUP_DIR=./backups
BACKUP_KEEP=7
```

### Production (MySQL + LAN)

```env
DEBUG=0
SECRET_KEY=replace-with-long-random-string
ALLOWED_HOSTS=192.168.1.10,helpdesk.example.com
CSRF_TRUSTED_ORIGINS=http://192.168.1.10:8000,https://helpdesk.example.com
SITE_URL=http://192.168.1.10:8000
DB_ENGINE=mysql
DB_NAME=mlamehticket
DB_USER=mlamehticket_user
DB_PASSWORD=strong-db-password
DB_HOST=localhost
DB_PORT=3306
TIME_ZONE=Asia/Riyadh
DEFAULT_SUPERADMIN_USERNAME=admin
DEFAULT_SUPERADMIN_EMAIL=admin@example.com
DEFAULT_SUPERADMIN_PASSWORD=strong-unique-bootstrap-password
BACKUP_DIR=./backups
BACKUP_KEEP=14
SESSION_COOKIE_AGE=259200
```

After saving `.env`, restart Daphne / `run-mlamehticket.ps1` so process env picks up changes.
