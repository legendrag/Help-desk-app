# Backup, restore, and database maintenance

How to back up, restore, and maintain the mlamehticket database and media files.

**Audience:** Operators and system administrators responsible for data durability and disaster recovery.

---

## Overview

mlamehticket provides two backup surfaces plus media export:

| Type | What it includes | Format | Restorable? |
|------|------------------|--------|-------------|
| Database backup (CLI) | Full database — tickets, users, settings, everything | `.sql` (MySQL) or `.sqlite3` (SQLite) | Yes |
| Tickets export (Web UI) | Tickets and chat messages in readable form | `.txt` | No — read-only archive |
| Media backup (Web UI) | Uploaded attachments and knowledge-base files | `.zip` | Yes |

The tickets text export from the web UI is for reading and archiving only. For a restorable backup, always use the `backup_db` management command.

Related docs: [Configuration](configuration.md) · [Deployment](deployment.md) · [Security hardening](security-hardening.md) · [Troubleshooting](troubleshooting.md)

---

## Backup methods

### Web UI (browser)

Go to **Settings → System Maintenance**. You need superuser access or a role with the “Manage System Maintenance” permission.

#### Export tickets and messages

- Click **Export Tickets & Messages**.
- Downloads a `.txt` file with tickets, details, and full chat history.
- Good for archiving, auditing, and sharing with management.
- **Not restorable** — this is a human-readable report, not a database dump.

#### Download media zip

- Click **Download Media Zip**.
- Downloads a `.zip` of everything under `media/`.
- Includes ticket attachments and knowledge-base files.
- **Restorable** — unzip back into the `media/` folder (see [Restoring media files](#restoring-media-files)).

#### Rate limit

Both download actions have a **5-minute cooldown per user** to prevent abuse. Downloads are logged with username, user ID, and IP address.

### CLI commands (terminal)

Run these from the project root (where `manage.py` lives), with the virtualenv activated.

#### Basic database backup

```bash
python manage.py backup_db
```

This will:

- Create a timestamped file under `./backups/` (or `BACKUP_DIR`).
- For SQLite: copy the database file (e.g. `backup_2026-07-04_020000.sqlite3`).
- For MySQL: run `mysqldump` (e.g. `backup_2026-07-04_020000.sql`). `mysqldump` must be on `PATH`.
- Delete older backups, keeping the most recent count from `--keep` / `BACKUP_KEEP` (default **7**).
- Run an integrity check on SQLite backups.

#### Customize backup settings

```bash
# Keep more backups (14 instead of default 7)
python manage.py backup_db --keep 14

# Save backups to a different directory (must be within the project root)
python manage.py backup_db --dir ./my_backups
```

The `--dir` path **must resolve inside the project root**. Paths outside the project are rejected for safety.

#### Environment variables

Defaults can be set in `.env` (see [Configuration](configuration.md)):

```env
BACKUP_DIR=./backups
BACKUP_KEEP=7
```

#### What gets created

```text
backups/
├── backup_2026-07-01_020000.sql
├── backup_2026-07-02_020000.sql
├── backup_2026-07-03_020000.sql
└── backup_2026-07-04_020000.sql    ← most recent
```

Oldest files are removed when the count exceeds the keep limit.

---

## Automated backups

### Linux (crontab)

```bash
crontab -e
```

Example jobs:

```bash
# Database backup — every day at 2:00 AM
0 2 * * * cd /path/to/mlamehticket-app && /path/to/venv/bin/python manage.py backup_db

# Notification cleanup — every day at 3:00 AM
0 3 * * * cd /path/to/mlamehticket-app && /path/to/venv/bin/python manage.py cleanup_notifications

# Orphan media cleanup — every Sunday at 4:00 AM
0 4 * * 0 cd /path/to/mlamehticket-app && /path/to/venv/bin/python manage.py cleanup_media --delete
```

Replace paths with your install and venv locations.

### Windows (Task Scheduler)

1. Open **Task Scheduler**.
2. Create a new task (run whether user is logged on or not, if appropriate).
3. Set the trigger (e.g. daily at 2:00 AM).
4. Set the action:
   - **Program:** `C:\path\to\mlamehticket-app\.venv\Scripts\python.exe`
   - **Arguments:** `manage.py backup_db`
   - **Start in:** `C:\path\to\mlamehticket-app`
5. Optionally add separate tasks for `cleanup_notifications` and `cleanup_media --delete`.

See also [Deployment](deployment.md) for production scheduling notes.

---

## Restore procedures

Stop the application before restoring a database or replacing media in place.

### Restoring MySQL database

#### Same server

```bash
# 1. Stop the application (stop Daphne / run-mlamehticket.ps1)

# 2. Import the backup
mysql -u root -p mlamehticket < backups/backup_2026-07-04_020000.sql

# 3. Start the application again
```

#### Brand-new server

```bash
mysql -u root -p
```

```sql
CREATE DATABASE mlamehticket CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'mlamehticket_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON mlamehticket.* TO 'mlamehticket_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

```bash
mysql -u root -p mlamehticket < backup_2026-07-04_020000.sql
mysql -u root -p -e "USE mlamehticket; SHOW TABLES;"
```

#### One table only (advanced)

```bash
# Extract one table from the dump (Linux/macOS)
sed -n '/^-- Table structure for table `tickets_ticket`/,/^-- Table structure for table/p' backup.sql > tickets_only.sql

mysql -u root -p mlamehticket < tickets_only.sql
```

### Restoring SQLite database

SQLite backups are file copies. Replace `db.sqlite3` only while the app is stopped:

```powershell
# Windows
copy backups\backup_2026-07-04_020000.sqlite3 db.sqlite3
```

```bash
# Linux/macOS
cp backups/backup_2026-07-04_020000.sqlite3 db.sqlite3
```

### Restoring media files

#### Windows (PowerShell)

```powershell
Remove-Item -Recurse -Force media
Expand-Archive -Path media_backup.zip -DestinationPath media -Force
```

#### Linux/macOS

```bash
rm -rf media
unzip -o media_backup.zip -d media/
```

---

## Full disaster recovery

Use this when the server is lost and you must rebuild from scratch.

### Step 1 — New server and project

```bash
# Example on Linux; on Windows use Python 3.12+ and optional MySQL 8
sudo apt update
sudo apt install python3 python3-pip python3-venv mysql-server git

git clone <your-repo-url> mlamehticket-app
cd mlamehticket-app

python3 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

On Windows you can also follow [Installation](installation.md) (manual venv or Windows installer).

### Step 2 — Environment

```bash
cp .env.example .env
# Edit .env with production values
```

Minimum production-oriented settings:

```env
SECRET_KEY=your-very-long-random-secret-key
DEBUG=0
DB_ENGINE=mysql
DB_NAME=mlamehticket
DB_USER=mlamehticket_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
ALLOWED_HOSTS=your-domain.com,192.168.1.10
SITE_URL=https://your-domain.com
DEFAULT_SUPERADMIN_PASSWORD=a-strong-unique-password
```

Full variable reference: [Configuration](configuration.md). Security checklist: [Security hardening](security-hardening.md).

### Step 3 — Database

```bash
mysql -u root -p -e "CREATE DATABASE mlamehticket CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

**Option A — Restore from a database backup** (preferred if you have one):

```bash
mysql -u root -p mlamehticket < backup_2026-07-04_020000.sql
```

**Option B — Fresh install** (no usable dump):

1. Set a **strong** `DEFAULT_SUPERADMIN_PASSWORD` in `.env` (not empty, and not `admin`, `password`, `changeme`, or `12345678`).
2. Run migrations. There is **no** `bootstrap_superadmin` management command. The bootstrap admin is created by a `post_migrate` signal in `accounts/signals.py` when the password is set and not weak:

```bash
python manage.py migrate
```

The new superuser is created with `requires_password_change=True` and must change password on first login.

When `DEBUG=0`, a weak or empty `DEFAULT_SUPERADMIN_PASSWORD` causes Django to refuse to start (`ImproperlyConfigured`).

### Step 4 — Media

```bash
unzip media_backup.zip -d media/
# or, if you have no media backup:
mkdir -p media
```

### Step 5 — Static files and start

```bash
python manage.py collectstatic --noinput
```

Production on Windows:

```powershell
.\run-mlamehticket.ps1
```

Or Daphne directly:

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Use Daphne (not `runserver`) so WebSockets for chat and push work. Details: [Deployment](deployment.md).

### Step 6 — Re-enable automated backups

Configure cron or Windows Task Scheduler as in [Automated backups](#automated-backups). Copy off-site backups of `.sql` / `.sqlite3`, media zips, and `.env` to a safe location.

---

## Cleanup and maintenance

### Ticket cleanup

Delete old closed tickets to free space.

**Web UI:** Settings → System Maintenance → Cleanup Old Tickets

- Choose a period (30 / 60 / 90 days, or 1 year).
- **Preview** counts tickets that would be removed.
- **Confirm Delete** removes them and their attachment files on disk.

There is no standalone CLI for ticket cleanup; use the web UI.

### Notification cleanup

**Web UI:** Settings → System Maintenance → Cleanup Notifications.

**CLI:**

```bash
# Default: delete read notifications older than 30 days, all older than 90 days
python manage.py cleanup_notifications

# Custom thresholds
python manage.py cleanup_notifications --read-days 14 --all-days 60

# Preview without deleting
python manage.py cleanup_notifications --dry-run
```

### Orphan media cleanup

Finds files under `media/` that are no longer referenced by any file field.

```bash
# Scan and report only (default — does not delete)
python manage.py cleanup_media

# Actually delete orphaned files
python manage.py cleanup_media --delete
```

---

## Best practices

### What to back up off-server

Keep copies **off the application server** (cloud storage, external drive, another host):

| Item | How to get it | How often |
|------|---------------|-----------|
| Database backup (`.sql` / `.sqlite3`) | `python manage.py backup_db` | Daily |
| Media files (`.zip`) | Web UI → Download Media Zip | Weekly |
| Environment file (`.env`) | Manual copy | After any change |
| VAPID private key (`private_key.pem` or env value) | Manual copy | After first generation / change |

### Recommended schedule

| Task | Frequency | Command / action |
|------|-----------|------------------|
| Database backup | Daily ~2 AM | `python manage.py backup_db` |
| Notification cleanup | Daily ~3 AM | `python manage.py cleanup_notifications` |
| Media orphan cleanup | Weekly (Sunday) | `python manage.py cleanup_media --delete` |
| Media zip backup | Weekly | Web UI download |
| Off-site copy | Weekly | Copy dump + zip + `.env` secrets off-box |

### Test restores

1. Copy a recent backup to a test machine.
2. Create a fresh database and import the dump (or replace SQLite).
3. Start the app and verify tickets, users, and settings.
4. Repeat at least monthly.

### Security

- Database backups contain all user data, including password hashes — treat them as secrets.
- Restrict filesystem ACLs on the backup directory.
- Never commit `.env` or `private_key.pem` to git.
- Web UI backup downloads are rate-limited and audited.

Tickets export from the web UI remains a **read-only archive**; it cannot rebuild the database.
