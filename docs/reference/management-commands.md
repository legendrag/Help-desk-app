# Management commands

Reference for every custom `manage.py` command shipped with mlamehticket: purpose, flags, and example invocations.

**Audience:** Operators and developers running maintenance from the project root.

Related: [Backup and restore](../operations/backup-restore.md) · [Installation](../operations/installation.md) · [Configuration](../operations/configuration.md)

Run all commands from the project root (where `manage.py` lives), with the virtualenv activated.

---

## backup_db

Create a timestamped database backup and enforce a retention policy.

| Flag | Default | Description |
|---|---|---|
| `--dir` | `./backups`, or `BACKUP_DIR` if set | Directory for backup files. Path must resolve **inside the project root**; paths outside are rejected. |
| `--keep` | `7`, or `BACKUP_KEEP` if set | Number of recent `backup_*` files to keep. Older files are deleted. |

### Behavior

- **SQLite:** copies the database file to `backup_YYYY-MM-DD_HHMMSS.sqlite3`, then runs `PRAGMA integrity_check`.
- **MySQL:** runs `mysqldump` (must be on `PATH`) to `backup_YYYY-MM-DD_HHMMSS.sql` with `--single-transaction`, `--routines`, and `--triggers`. Password is passed via `MYSQL_PWD` when configured.
- Other database engines raise an error.

Full restore procedures: [Backup and restore](../operations/backup-restore.md).

### Examples

PowerShell:

```powershell
python manage.py backup_db
python manage.py backup_db --keep 14
python manage.py backup_db --dir .\my_backups --keep 14
$env:BACKUP_DIR = ".\backups"
$env:BACKUP_KEEP = "10"
python manage.py backup_db
```

Bash:

```bash
python manage.py backup_db
python manage.py backup_db --keep 14
python manage.py backup_db --dir ./my_backups --keep 14
BACKUP_DIR=./backups BACKUP_KEEP=10 python manage.py backup_db
```

---

## cleanup_notifications

Delete old in-app notifications to keep the notifications table lean.

| Flag | Default | Description |
|---|---|---|
| `--read-days` | `30` | Delete **read** notifications older than this many days. |
| `--all-days` | `90` | Delete **all** notifications (read or unread) older than this many days. |
| `--dry-run` | off | Report what would be deleted without deleting. |

### Behavior

1. Deletes every notification older than `--all-days`.
2. Then deletes remaining **read** notifications older than `--read-days`.

Order matters so counts are not double-counted incorrectly against the all-days cutoff.

### Examples

PowerShell:

```powershell
python manage.py cleanup_notifications
python manage.py cleanup_notifications --dry-run
python manage.py cleanup_notifications --read-days 14 --all-days 60
```

Bash:

```bash
python manage.py cleanup_notifications
python manage.py cleanup_notifications --dry-run
python manage.py cleanup_notifications --read-days 14 --all-days 60
```

---

## cleanup_media

Find files under `MEDIA_ROOT` that are not referenced by any `FileField` / `ImageField` in the database.

| Flag | Default | Description |
|---|---|---|
| *(none)* | dry-run | Lists orphaned files and total size; does **not** delete. |
| `--delete` | off | Actually remove orphaned files, then remove empty directories left behind. |

Always run without `--delete` first and review the report.

### Examples

PowerShell:

```powershell
python manage.py cleanup_media
python manage.py cleanup_media --delete
```

Bash:

```bash
python manage.py cleanup_media
python manage.py cleanup_media --delete
```

---

## seed_demo_data

Seed demo roles, users, organization data, tickets, KB articles, news, and notifications for local development or demos.

| Flag | Default | Description |
|---|---|---|
| `--clear` | off | Remove previously seeded demo data before seeding again. |
| `--password` | `demo1234` | Password for demo users. |
| `--skip-tickets` | off | Skip ticket and message seeding. |
| `--skip-notifications` | off | Skip in-app notification seeding. |
| `--ticket-count` | none | Generate approximately N additional tickets for performance testing. Curated demo tickets are always created first. Use with `--clear` for a fresh bulk seed. |

### Passwords

- Demo users use `--password` (default `demo1234`).
- The bootstrap **admin** password still comes from `DEFAULT_SUPERADMIN_PASSWORD` in `.env` (not from `--password`).

Do not use this command against a production database with real data.

### Examples

PowerShell:

```powershell
python manage.py seed_demo_data
python manage.py seed_demo_data --clear
python manage.py seed_demo_data --password "LocalDemo!2026"
python manage.py seed_demo_data --clear --skip-tickets --skip-notifications
python manage.py seed_demo_data --clear --ticket-count 500
```

Bash:

```bash
python manage.py seed_demo_data
python manage.py seed_demo_data --clear
python manage.py seed_demo_data --password 'LocalDemo!2026'
python manage.py seed_demo_data --clear --skip-tickets --skip-notifications
python manage.py seed_demo_data --clear --ticket-count 500
```

### Performance Seeding

For performance testing with ~500 tickets, use:

```bash
python manage.py seed_demo_data --clear --ticket-count 500
```

This will:
- Clear existing demo data
- Create the standard curated demo tickets (8 tickets)
- Generate approximately 500 additional varied tickets
- Total tickets: ~508

The generated tickets vary in:
- Status (Open, In Progress, Waiting, Closed)
- Priority (Low, Medium, High, Urgent)
- Branch (Main, North, South, East)
- Department and Category
- Age (1-240 hours old)
- About 40% include follow-up messages

**Timing:**
- **SQLite:** ~2.5 minutes (139-150 s)
- **MySQL:** ~2.5 minutes (148 s)

For MySQL performance testing setup, see [MySQL Performance Testing Setup](#mysql-performance-testing-setup) below.

---

## MySQL Performance Testing Setup

For local performance testing with MySQL (recommended for replicating production page-load behavior):

### Prerequisites

- MySQL 8.0+ installed and running locally
- PyMySQL already in requirements.txt (no additional packages needed)

### Quick setup

1. **Create the database:**

```bash
# Log in to MySQL as root or admin user
mysql -u root -p

# Create database and user
CREATE DATABASE mlamehticket CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'mlamehticket_user'@'localhost' IDENTIFIED BY 'your_password_here';
GRANT ALL PRIVILEGES ON mlamehticket.* TO 'mlamehticket_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

2. **Configure `.env` for MySQL:**

```env
DB_ENGINE=mysql
DB_NAME=mlamehticket
DB_USER=mlamehticket_user
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=3306
```

3. **Migrate and seed:**

```bash
python manage.py migrate
python manage.py seed_demo_data --clear --ticket-count 500
```

4. **Run the development server:**

```bash
python manage.py runserver 0.0.0.0:8000
```

### Switching back to SQLite

Update `.env`:

```env
DB_ENGINE=sqlite
```

Then migrate and optionally re-seed:

```bash
python manage.py migrate
python manage.py seed_demo_data --clear --ticket-count 500
```

### Optional: Docker MySQL

If you prefer not to install MySQL directly:

```bash
# Start MySQL in Docker
docker run --name mlameh-mysql \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=mlamehticket \
  -e MYSQL_USER=mlamehticket_user \
  -e MYSQL_PASSWORD=your_password_here \
  -p 3306:3306 \
  -d mysql:8.0 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_unicode_ci

# Wait for MySQL to start (~10-30 seconds)
docker logs -f mlameh-mysql
# (Press Ctrl+C once you see "ready for connections")

# Use the same .env settings as above, then migrate and seed
```

Stop the container when done: `docker stop mlameh-mysql` (data persists).  
Remove it entirely: `docker rm -v mlameh-mysql`.

---

## Scheduling tips

| Command | Typical use |
|---|---|
| `backup_db` | Daily or more often via Task Scheduler / cron; see [Backup and restore](../operations/backup-restore.md) |
| `cleanup_notifications` | Weekly; start with `--dry-run` |
| `cleanup_media` | Occasional; always dry-run first |
| `seed_demo_data` | Dev/demo only |

Help for any command:

```bash
python manage.py help backup_db
python manage.py help cleanup_notifications
python manage.py help cleanup_media
python manage.py help seed_demo_data
```
