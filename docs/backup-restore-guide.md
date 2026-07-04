# Help Desk App — Backup, Restore & Database Management Guide

---

## Table of Contents

1. [Overview](#overview)
2. [Backup Methods](#backup-methods)
   - [Web UI (Browser)](#web-ui-browser)
   - [CLI Commands (Terminal)](#cli-commands-terminal)
3. [Automated Backups (Cron Jobs)](#automated-backups-cron-jobs)
4. [Restore Procedures](#restore-procedures)
   - [Restoring MySQL Database](#restoring-mysql-database)
   - [Restoring SQLite Database](#restoring-sqlite-database)
   - [Restoring Media Files](#restoring-media-files)
5. [Full Disaster Recovery](#full-disaster-recovery)
6. [Cleanup & Maintenance](#cleanup--maintenance)
   - [Ticket Cleanup](#ticket-cleanup)
   - [Notification Cleanup](#notification-cleanup)
   - [Orphan Media Cleanup](#orphan-media-cleanup)
7. [Best Practices](#best-practices)

---

## Overview

The Help Desk app provides two types of backups:

| Type | What It Includes | Format | Restorable? |
|------|-----------------|--------|-------------|
| **Database backup** (CLI) | Full database — all tickets, users, settings, everything | `.sql` (MySQL) or `.sqlite3` (SQLite) | ✅ Yes |
| **Tickets export** (Web UI) | Tickets and chat messages in readable format | `.txt` | ❌ No (read-only archive) |
| **Media backup** (Web UI) | All uploaded attachments and files | `.zip` | ✅ Yes |

> **Important:** The tickets text export from the web UI is for reading and archiving only.
> For a restorable backup, always use the `backup_db` CLI command.

---

## Backup Methods

### Web UI (Browser)

Go to **Settings → System Maintenance** in the app. You need superuser access or
a role with "Manage System Maintenance" permission.

#### Export Tickets & Messages
- Click **"Export Tickets & Messages"**
- Downloads a `.txt` file with all tickets, their details, and full chat history
- Good for: archiving, auditing, sharing with management
- **Not restorable** — this is a human-readable report, not a database dump

#### Download Media Zip
- Click **"Download Media Zip"**
- Downloads a `.zip` file containing everything in the `media/` folder
- Includes: ticket attachments, knowledge base files
- **Restorable** — just unzip back to the `media/` folder

#### Rate Limit
- Both download buttons have a 5-minute cooldown per user to prevent abuse


### CLI Commands (Terminal)

These commands are run from the project root directory (where `manage.py` is).

#### Basic Database Backup

```bash
python manage.py backup_db
```

This will:
- Create a timestamped backup file in the `./backups/` directory
- For SQLite: copies the database file (e.g., `backup_2026-07-04_020000.sqlite3`)
- For MySQL: runs `mysqldump` (e.g., `backup_2026-07-04_020000.sql`)
- Automatically deletes old backups, keeping the most recent 7
- Runs an integrity check on SQLite backups

#### Customize Backup Settings

```bash
# Keep more backups (14 instead of default 7)
python manage.py backup_db --keep 14

# Save backups to a different directory (must be within the project)
python manage.py backup_db --dir ./my_backups
```

#### Environment Variables

You can also set defaults via your `.env` file:

```env
BACKUP_DIR=./backups
BACKUP_KEEP=7
```

#### What Gets Created

```
backups/
├── backup_2026-07-01_020000.sql
├── backup_2026-07-02_020000.sql
├── backup_2026-07-03_020000.sql
└── backup_2026-07-04_020000.sql    ← most recent
```

The oldest files are automatically deleted when the count exceeds the `--keep` limit.

---

## Automated Backups (Cron Jobs)

For production servers, set up cron jobs to run backups automatically.

### Linux (crontab)

Open crontab:
```bash
crontab -e
```

Add these lines:
```bash
# Database backup — every day at 2:00 AM
0 2 * * * cd /path/to/Help-desk-app && /path/to/venv/bin/python manage.py backup_db

# Notification cleanup — every day at 3:00 AM
0 3 * * * cd /path/to/Help-desk-app && /path/to/venv/bin/python manage.py cleanup_notifications

# Orphan media cleanup — every Sunday at 4:00 AM
0 4 * * 0 cd /path/to/Help-desk-app && /path/to/venv/bin/python manage.py cleanup_media --delete
```

### Windows (Task Scheduler)

1. Open **Task Scheduler**
2. Create a new task
3. Set the trigger (e.g., daily at 2:00 AM)
4. Set the action:
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `manage.py backup_db`
   - Start in: `C:\path\to\Help-desk-app`

---

## Restore Procedures

### Restoring MySQL Database

#### Scenario: Restore to the same server

```bash
# 1. Stop the application

# 2. Import the backup
mysql -u root -p helpdesk < backups/backup_2026-07-04_020000.sql

# 3. Start the application
```

#### Scenario: Restore to a brand new server

```bash
# 1. Log into MySQL
mysql -u root -p

# 2. Create the database
CREATE DATABASE helpdesk CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 3. Create the app user (if needed)
CREATE USER 'helpdesk_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON helpdesk.* TO 'helpdesk_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# 4. Import the backup
mysql -u root -p helpdesk < backup_2026-07-04_020000.sql

# 5. Verify it worked
mysql -u root -p -e "USE helpdesk; SHOW TABLES;"
```

#### Scenario: Restore a specific table only

```bash
# Extract just one table from the backup (Linux/Mac)
sed -n '/^-- Table structure for table `tickets_ticket`/,/^-- Table structure for table/p' backup.sql > tickets_only.sql

# Import just that table
mysql -u root -p helpdesk < tickets_only.sql
```


### Restoring SQLite Database

SQLite backups are simple file copies:

```powershell
# Windows
copy backups\backup_2026-07-04_020000.sqlite3 db.sqlite3
```

```bash
# Linux/Mac
cp backups/backup_2026-07-04_020000.sqlite3 db.sqlite3
```

> Make sure the application is stopped before replacing the database file.


### Restoring Media Files

#### Windows (PowerShell)

```powershell
# Remove old media folder (optional, for clean restore)
Remove-Item -Recurse -Force media

# Unzip the backup
Expand-Archive -Path media_backup.zip -DestinationPath media -Force
```

#### Linux/Mac

```bash
# Remove old media folder (optional)
rm -rf media

# Unzip the backup
unzip -o media_backup.zip -d media/
```

---

## Full Disaster Recovery

If the server is completely lost and you need to rebuild from scratch:

### Step 1: Set up the new server

```bash
# Install system dependencies
sudo apt update
sudo apt install python3 python3-pip python3-venv mysql-server git

# Clone the project
git clone <your-repo-url> Help-desk-app
cd Help-desk-app

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### Step 2: Configure the environment

```bash
# Copy your saved .env file, or create a new one from the example
cp .env.example .env

# Edit the .env file with your production values
nano .env
```

Key settings to configure in `.env`:
```env
SECRET_KEY=your-very-long-random-secret-key
DEBUG=0
DB_ENGINE=mysql
DB_NAME=helpdesk
DB_USER=helpdesk_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
ALLOWED_HOSTS=your-domain.com
```

### Step 3: Set up the database

```bash
# Create the MySQL database
mysql -u root -p -e "CREATE DATABASE helpdesk CHARACTER SET utf8mb4;"

# Option A: Restore from backup (if you have one)
mysql -u root -p helpdesk < backup_2026-07-04_020000.sql

# Option B: Fresh install (if no backup available)
python manage.py migrate
python manage.py bootstrap_superadmin
```

### Step 4: Restore media files

```bash
# If you have a media backup
unzip media_backup.zip -d media/

# If not, create the empty directory
mkdir -p media
```

### Step 5: Collect static files and start

```bash
python manage.py collectstatic --noinput

# Start with your production server (e.g., daphne for ASGI)
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### Step 6: Set up automated backups on the new server

```bash
crontab -e
# Add: 0 2 * * * cd /path/to/Help-desk-app && .venv/bin/python manage.py backup_db
```

---

## Cleanup & Maintenance

### Ticket Cleanup

Delete old closed tickets to free database space.

**Web UI:** Settings → System Maintenance → Cleanup Old Tickets
- Select a time period (30 days, 60 days, 90 days, or 1 year)
- Click "Preview" to see how many tickets would be deleted
- Click "Confirm Delete" to proceed
- Also removes attachment files from disk for deleted tickets

**CLI:** Not available as a standalone command (use the web UI).


### Notification Cleanup

Delete old in-app notifications.

**Web UI:** Settings → System Maintenance → Cleanup Notifications
- Choose thresholds for read notifications and all notifications
- Click "Delete"

**CLI:**
```bash
# Default: delete read > 30 days, all > 90 days
python manage.py cleanup_notifications

# Custom thresholds
python manage.py cleanup_notifications --read-days 14 --all-days 60

# Preview without deleting
python manage.py cleanup_notifications --dry-run
```


### Orphan Media Cleanup

Find and remove uploaded files that are no longer referenced in the database
(e.g., from deleted tickets).

**CLI:**
```bash
# Scan and report (does NOT delete anything)
python manage.py cleanup_media

# Actually delete orphaned files
python manage.py cleanup_media --delete
```

---

## Best Practices

### What to Back Up

Always keep copies of these three things **off the server** (cloud storage, 
external drive, another machine):

| Item | How to get it | How often |
|------|--------------|-----------|
| Database backup (`.sql`) | `python manage.py backup_db` | Daily |
| Media files (`.zip`) | Web UI → Download Media Zip | Weekly |
| Environment file (`.env`) | Manual copy | After any change |

### Backup Schedule Recommendations

| Task | Frequency | Command |
|------|-----------|---------|
| Database backup | Daily at 2 AM | `python manage.py backup_db` |
| Notification cleanup | Daily at 3 AM | `python manage.py cleanup_notifications` |
| Media orphan cleanup | Weekly (Sunday) | `python manage.py cleanup_media --delete` |
| Media zip backup | Weekly (manual) | Web UI download |
| Off-site backup copy | Weekly | Copy `.sql` + `.zip` to cloud storage |

### Testing Your Backups

Backups are useless if they don't actually work. Test them periodically:

1. Copy a recent backup to a test machine
2. Set up a fresh database and import the backup
3. Start the app and verify data is intact
4. Do this at least once a month

### Security Reminders

- The database backup contains **all user data**, including password hashes. 
  Treat backup files as sensitive.
- Store backups in a location with restricted access.
- The `.env` file contains database passwords and the Django secret key. 
  Never commit it to git.
- Backup downloads are rate-limited (5-minute cooldown) and logged with the
  username, user ID, and IP address.
