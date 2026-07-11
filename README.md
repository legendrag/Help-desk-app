# DeskPlus

DeskPlus is a modern, high-performance ticket management platform built with **Django**, **HTMX**, and **Vanilla JavaScript**.

## Core Architecture
- **Backend:** Python + Django (Monolithic Server-Side Rendering)
- **Frontend:** HTML5, Vanilla CSS3, Vanilla JavaScript, HTMX (for dynamic updates)
- **Real-time:** Django Channels + WebSockets (Chat & Notifications)
- **Database:** MySQL (Production) / SQLite (Development)
- **Authentication:** Django Session-Based Authentication

## Key Features
- **Real-time Chat:** Instant messaging within ticket details.
- **Push Notifications:** Browser-native and in-app notifications for ticket updates.
- **Smart Routing:** Automated category/branch/department ticket management.
- **Performance Metrics:** Built-in tracking for response and resolution times.
- **PWA Ready:** Modern responsive design that works on mobile and desktop.

## Project Structure
- `accounts/`: User management and session authentication.
- `tickets/`: Core ticket lifecycle, views, and business logic.
- `notifications/`: WebSocket consumers and notification signals.
- `config/`: Global project settings and URL routing.
- `static/`: Global CSS/JS assets (including `chat.js`, `notifications.js`).
- `templates/`: Server-side HTML templates (Base & Component-based).

## Quick Start

### 1) Prerequisites
- **Python 3.12+**
- **Virtual Environment:** Recommended to use `.venv`.

### 2) Setup & Run
```powershell
# 1. Create and activate virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file (copy from .env.example)
cp .env.example .env

# 4. Migrate database
python manage.py migrate

# 5. Start Server
python manage.py runserver
```

### 3) Initial Access
- **URL:** `http://localhost:8000`
- **Default Admin:** `admin` / `admin`

## Environment Variables (`.env`)

| Variable | Description | Default |
|---|---|---|
| `DEBUG` | Enable/Disable debug mode | `1` |
| `SECRET_KEY` | Django unique secret key | `change-me` |
| `DB_ENGINE` | `sqlite` or `mysql` | `sqlite` |
| `DB_NAME` | Database name | `deskplus` |
| `DB_HOST` | Database host | `localhost` |
| `DB_PORT` | Database port | `3306` |
| `DB_USER` | Database user | `root` |
| `DB_PASSWORD` | Database password | *(empty)* |
| `DB_CONN_MAX_AGE` | Persistent connection lifetime (seconds) | `600` |
| `ALLOWED_HOSTS` | Server hostnames | `*` |
| `BACKUP_DIR` | Backup storage directory | `./backups` |
| `BACKUP_KEEP` | Number of backups to retain | `7` |

## Production Database Setup (MySQL)

SQLite is used by default for development. For production, switch to MySQL:

### 1) Install MySQL 8.0+

Ensure the database uses **utf8mb4** charset:
```sql
CREATE DATABASE deskplus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2) Configure `.env`
```env
DB_ENGINE=mysql
DB_NAME=deskplus
DB_USER=deskplus_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=3306
```

### 3) Run Migrations
```bash
python manage.py migrate
```

> **Note:** The MySQL config includes `CONN_MAX_AGE=600` (10 min persistent connections) and `CONN_HEALTH_CHECKS=True` for optimal performance with Django Channels / Daphne.

## Database Maintenance

### Backup
```bash
# Create a backup (SQLite: file copy, MySQL: mysqldump)
python manage.py backup_db

# Keep 14 backups instead of the default 7
python manage.py backup_db --keep 14

# Store in a custom directory
python manage.py backup_db --dir /path/to/backups
```

### Notification Cleanup
```bash
# Delete read notifications >30 days old, all notifications >90 days old
python manage.py cleanup_notifications

# Preview what would be deleted
python manage.py cleanup_notifications --dry-run

# Custom retention periods
python manage.py cleanup_notifications --read-days 14 --all-days 60
```

### Recommended Scheduled Tasks
| Task | Schedule | Command |
|---|---|---|
| Database backup | Daily at 2:00 AM | `python manage.py backup_db` |
| Notification cleanup | Daily at 3:00 AM | `python manage.py cleanup_notifications` |

## Documentation
- [Gmail Setup](docs/GMAIL_APP_PASSWORD.md)
- [Deployment Guide](docs/deployment_guide.md)
- [Refactor Task](docs/refactor/task.md)
