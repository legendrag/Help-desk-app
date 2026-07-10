# Walkthrough: DeskPlus Refactoring

## Overview
The DeskPlus system has been successfully refactored from a separate React frontend and Django REST API into a **monolithic Django application**. This simplifies deployment, improves development speed, and leverages Django's built-in features more effectively.

## Key Accomplishments

### 1. Unified Architecture
- **Monolithic Structure:** All code (views, templates, static files) now lives in the project root.
- **Server-Side Rendering:** React has been replaced by Django Templates and HTMX for a faster, simpler user experience.
- **Session-Based Auth:** Switched from JWT to standard Django sessions for better security and integration.

### 2. Progressive Web App (PWA) & Web Push
- **Installable App:** The application now features a Web App Manifest (`manifest.json`) allowing it to be installed as a standalone app on desktops and mobile devices.
- **Native Notifications:** Integrated `django-webpush` and a custom Service Worker (`sw.js`) to support native OS-level push notifications, even when the browser tab is closed.

### 3. Environment Compatibility
- **Windows Portability:** Replaced `mysqlclient` with `PyMySQL` to ensure the project installs easily on Windows machines without requiring C++ Build Tools.
- **Cleaner Requirements:** Removed all DRF, JWT, and CORS-related packages, reducing the dependency footprint.

### 4. Updated Documentation & Scripts
- **Modernized README:** Reflects the new single-command startup and simplified architecture.
- **PowerShell Helpers:** `test-local.ps1` and `run-deskplus.ps1` are now optimized for the root-level monolith.
- **Installer Integration:** Updated Inno Setup scripts (`build.ps1`, `setup.iss`, `install.ps1`) to package and deploy the unified codebase.

## VAPID Keys for Production
To support Web Push notifications, a set of VAPID (Voluntary Application Server Identification) keys are required. During development, a pair was generated (`public_key.pem` and `private_key.pem`).

> [!WARNING]
> Do NOT commit your production `private_key.pem` to version control! 

When deploying to production or cloning the repository elsewhere:
1. You can generate a new set of keys by running: `vapid --gen`
2. This will create a new `private_key.pem` and `public_key.pem` in your directory.
3. Ensure these keys are read by Django via the `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` environment variables, or simply leave the `pem` files in the project root.

## How to Run Now
1.  **Activate Environment:** `.\.venv\Scripts\Activate.ps1`
2.  **Start Dev Server:** `python manage.py runserver`
3.  **Access App:** `http://localhost:8000`

## Verification
- [x] Authentication and Password Change
- [x] Ticket Lifecycle (Create, Claim, Resolve)
- [x] Real-time Notifications (WebSockets & Web Push PWA)
- [x] Real-time Messaging
- [x] Database Connectivity (MySQL/SQLite)
