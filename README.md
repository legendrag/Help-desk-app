# Help Desk Ticket System

A modern, high-performance monolithic Help Desk system built with **Django**, **HTMX**, and **Vanilla JavaScript**.

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
python -m venv .venv
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
| `DB_NAME` | Database name | `helpdesk` |
| `ALLOWED_HOSTS` | Server hostnames | `*` |

## Documentation
- [Gmail Setup](docs/GMAIL_APP_PASSWORD.md)
- [Deployment Guide](docs/deployment_guide.md)
- [Refactor Task](docs/refactor/task.md)
