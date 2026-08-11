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
```

Bash:

```bash
python manage.py seed_demo_data
python manage.py seed_demo_data --clear
python manage.py seed_demo_data --password 'LocalDemo!2026'
python manage.py seed_demo_data --clear --skip-tickets --skip-notifications
```

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
