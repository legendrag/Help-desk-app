# Deployment

Production deployment for mlamehticket on Windows (and equivalent manual Linux setups) with MySQL and Daphne.

**Audience:** Operators deploying or upgrading a live help-desk instance.

---

## What you are deploying

mlamehticket is a **Django 6 monolith** with:

- **Channels + Daphne (ASGI)** for HTTP and WebSockets (live chat / notifications)
- **PyMySQL** for MySQL
- **WhiteNoise** for static files
- **InMemoryChannelLayer** (no Redis or Celery in the default stack)

Use Daphne in production — not `manage.py runserver` — so WebSockets work reliably. The Windows launcher is `run-mlamehticket.ps1`.

Prerequisites and first-time install: [Installation](installation.md). Env reference: [Configuration](configuration.md). Checklist: [Security hardening](security-hardening.md). Backups: [Backup and restore](backup-restore.md).

---

## 1. Create the MySQL database

Create the schema **before** the first migrate, with utf8mb4 so Arabic and emoji survive:

```sql
CREATE DATABASE mlamehticket CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Optional dedicated user:

```sql
CREATE USER 'mlamehticket_user'@'localhost' IDENTIFIED BY 'strong-db-password';
GRANT ALL PRIVILEGES ON mlamehticket.* TO 'mlamehticket_user'@'localhost';
FLUSH PRIVILEGES;
```

You can use MySQL Workbench, phpMyAdmin, or the `mysql` CLI. Wrong charset often shows up as garbled Arabic — see [Troubleshooting](troubleshooting.md).

---

## 2. Configure `.env` for production

```powershell
copy .env.example .env
# Edit .env
```

Minimum production-oriented values:

```env
DEBUG=0
SECRET_KEY=replace-with-a-long-random-secret
ALLOWED_HOSTS=192.168.1.10,helpdesk.example.com
CSRF_TRUSTED_ORIGINS=http://192.168.1.10:8000,https://helpdesk.example.com
SITE_URL=http://192.168.1.10:8000

DB_ENGINE=mysql
DB_NAME=mlamehticket
DB_USER=mlamehticket_user
DB_PASSWORD=strong-db-password
DB_HOST=localhost
DB_PORT=3306

DEFAULT_SUPERADMIN_USERNAME=admin
DEFAULT_SUPERADMIN_EMAIL=admin@example.com
DEFAULT_SUPERADMIN_PASSWORD=strong-unique-bootstrap-password

BACKUP_DIR=./backups
BACKUP_KEEP=14
```

Reminders:

- **`DEBUG=0`** — never leave debug on in production.
- **`SECRET_KEY`** — unique, long, random; never reuse the example value.
- **`DB_ENGINE=mysql`** — required for the production path (installer also sets this).
- **`DEFAULT_SUPERADMIN_PASSWORD`** — must be strong when `DEBUG=0` or Django will refuse to start. There is no `bootstrap_superadmin` command; migrate creates the admin via `post_migrate`.
- **`SITE_URL`** — must match how users open the app so email links work.
- **SMTP stays out of `.env`** — configure `EmailSetting` in the UI after login.

Full table: [Configuration](configuration.md).

---

## 3. Install dependencies, migrate, collect static

With the venv active (or after Windows installer `install.ps1`):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

`migrate` applies schema changes and, when the bootstrap password is set and not weak, creates the initial superuser with `requires_password_change=True`.

Do **not** run `seed_demo_data` on a real customer database unless you intentionally want demo records.

---

## 4. Start production with Daphne

### Recommended: `run-mlamehticket.ps1`

```powershell
.\run-mlamehticket.ps1
# or without opening a browser:
.\run-mlamehticket.ps1 -NoBrowser
```

The script:

1. Loads `.env` into the process environment.
2. Requires `.venv\Scripts\python.exe`.
3. Starts **Daphne** on **`0.0.0.0:8000`** with `config.asgi:application`.
4. Sets `ASGI_THREADS=200` to reduce static-file blocking under load.
5. Optionally opens `http://localhost:8000` after a short delay.

### Equivalent manual command

```powershell
.\.venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### Why Daphne (not `runserver`)

| Concern | `runserver` | Daphne |
|---------|-------------|--------|
| WebSockets (chat, live notifications) | Unreliable / not production | Designed for ASGI + WebSockets |
| Concurrent load | Dev-oriented | Production ASGI server |
| Unified HTTP + realtime | Limited | Single process serves both |

Local convenience scripts (`test-local.ps1`) intentionally use `runserver` for SQLite development. Production must use Daphne / `run-mlamehticket.ps1`.

---

## 5. LAN access and firewall

Binding to `0.0.0.0` allows other machines on the network to connect.

1. Find the server IP (e.g. `192.168.1.10`).
2. Open **inbound TCP port 8000** in Windows Firewall (or your host firewall).
3. Browse to `http://192.168.1.10:8000`.
4. Set `ALLOWED_HOSTS` to include that IP/hostname, `SITE_URL` to the same base URL, and `CSRF_TRUSTED_ORIGINS` to the full origin including scheme and port when needed.

Example firewall rule (PowerShell, elevated):

```powershell
New-NetFirewallRule -DisplayName "mlamehticket HTTP" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

---

## 6. Schedule backups and cleanup

Use **Windows Task Scheduler** (or cron on Linux) so maintenance runs without manual login.

### Database backup (daily)

- Program: `C:\path\to\mlamehticket\.venv\Scripts\python.exe`
- Arguments: `manage.py backup_db`
- Start in: `C:\path\to\mlamehticket`
- Trigger: daily at 02:00

### Notification cleanup (daily)

- Arguments: `manage.py cleanup_notifications`
- Trigger: daily at 03:00

### Orphan media (weekly, optional)

- Arguments: `manage.py cleanup_media --delete`
- Trigger: weekly (e.g. Sunday 04:00)
- Prefer a dry run first: `manage.py cleanup_media` (no `--delete`)

Copy backup files and media zips **off the server**. Full procedures: [Backup and restore](backup-restore.md).

---

## 7. Post-deploy checklist

1. Log in as bootstrap admin → complete forced password change.
2. Configure **EmailSetting** (SMTP) and send a test message.
3. Confirm `SITE_URL` links in that email open correctly.
4. Spot-check WebSocket chat between two browsers/users.
5. Confirm static assets load (WhiteNoise + `collectstatic`).
6. Confirm media uploads (see [Troubleshooting](troubleshooting.md) if `/media/` 404s with `DEBUG=0`).
7. Enable scheduled `backup_db` and verify a dump appears under `BACKUP_DIR`.
8. Review [Security hardening](security-hardening.md).

---

## Windows installer route (summary)

For the packaged offline install:

1. Build: `.\installer\fetch-payload.ps1` then `.\installer\build.ps1` → `installer\Output\mlamehticketSetup.exe` (+ `.sha256`).
2. On the client, run the Setup EXE as Administrator (SmartScreen: **More info → Run anyway** if unsigned).
3. Wizard chooses install dir, server address/port/admin email; MySQL credentials only if an existing server is detected.
4. `install.ps1` provisions Python/MySQL as needed, writes a full production `.env`, migrates, registers **mlamehticketApp** (Daphne) as a delayed auto-start service.
5. Use **FIRST-LOGIN.txt** for the bootstrap password; change it on first login.
6. To roll a new version: bump `VERSION`, rebuild, run the new EXE (upgrade mode backs up DB + code first).

More detail: [Installation](installation.md) · [installer/README.md](../../installer/README.md).

---

## Related documentation

| Topic | Doc |
|-------|-----|
| Env vars | [Configuration](configuration.md) |
| Secrets and hardening | [Security hardening](security-hardening.md) |
| Backup / restore / DR | [Backup and restore](backup-restore.md) |
| Failures after deploy | [Troubleshooting](troubleshooting.md) |
