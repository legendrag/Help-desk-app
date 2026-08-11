# Installation

Install and run mlamehticket for local development or as a Windows production package.

**Audience:** Operators and developers setting up a new environment for the first time.

---

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | **3.12+** | Required for manual/dev installs; **bundled** by the offline Windows installer when missing |
| Operating system | Windows 10/11 (64-bit) | Primary supported deploy target; Linux works for manual installs |
| MySQL Server | **8.0+** (optional for local) | Required for production; **bundled** by the offline installer when no existing server is used; local dev can use SQLite |
| Disk / network | ~2.5 GB free for offline install | LAN access needs firewall open on the chosen app port (default **8000**) |

Optional for **building** the Windows installer: **Inno Setup 6** and a one-time `.\installer\fetch-payload.ps1` (internet).

Stack overview: Django 6, Channels + Daphne (ASGI), PyMySQL, WhiteNoise, in-memory channel layer (no Redis or Celery). SMTP is configured in the database (`EmailSetting`), not in `.env`.

Next steps after install: [Configuration](configuration.md) · [Deployment](deployment.md)

---

## Manual setup (development)

Use this when working from a git checkout or source tree.

### 1. Clone or unpack the project

```powershell
cd d:\project\app
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Create `.env`

```powershell
copy .env.example .env
```

For local development, the defaults are usually enough:

- `DEBUG=1`
- `DB_ENGINE=sqlite`
- `SITE_URL=http://localhost:8000`

Set a strong `DEFAULT_SUPERADMIN_PASSWORD` if you want migrate to create the bootstrap admin (see [First login and bootstrap admin](#first-login-and-bootstrap-admin)). Leave it empty to skip auto-create during development.

Full variable list: [Configuration](configuration.md).

### 4. Migrate (and optional demo data)

```powershell
python manage.py migrate
python manage.py seed_demo_data
```

`seed_demo_data` options:

```powershell
python manage.py seed_demo_data --clear
python manage.py seed_demo_data --password demo1234
python manage.py seed_demo_data --skip-tickets
python manage.py seed_demo_data --skip-notifications
```

- `--clear` — remove previously seeded demo data before seeding again.
- `--password` — password for demo users (default `demo1234`). The bootstrap admin still uses `DEFAULT_SUPERADMIN_PASSWORD` from `.env`.
- `--skip-tickets` / `--skip-notifications` — omit those demo datasets.

### 5. Run the development server

```powershell
python manage.py runserver 0.0.0.0:8000
```

`runserver` is fine for local UI work. For production-like WebSockets, use Daphne via `run-mlamehticket.ps1` (see [Deployment](deployment.md)).

---

## Quick local launcher: `test-local.ps1`

From the project root:

```powershell
.\test-local.ps1
.\test-local.ps1 -InstallDeps
.\test-local.ps1 -Fresh -NoBrowser
.\test-local.ps1 -SkipI18nCheck
```

| Flag | Effect |
|------|--------|
| *(none)* | Ensure `.env`, venv, migrate SQLite, seed if DB is new, start `runserver` on `0.0.0.0:8000`, open browser |
| `-InstallDeps` | Install/upgrade packages from `requirements.txt` (also runs automatically if Django is missing from the venv) |
| `-Fresh` | Delete `db.sqlite3`, remigrate, and re-seed demo data |
| `-NoBrowser` | Do not open the browser |
| `-SkipI18nCheck` | Skip Arabic catalog compile/check (`scripts/i18n.py`) |

By default the script:

1. Creates `.env` from `.env.example` if missing.
2. Creates `.venv` if missing.
3. Optionally compiles/checks translations (`python scripts\i18n.py compile` / `check`) so missing Arabic strings fail loudly instead of silently showing English.
4. Runs `migrate` with SQLite.
5. Runs `seed_demo_data` when the database is new or `-Fresh` was used.
6. Starts `python manage.py runserver 0.0.0.0:8000`.

If the i18n check fails, fix with `python scripts\i18n.py update` (translate), then `compile`, or bypass temporarily with `-SkipI18nCheck`. See [Troubleshooting](troubleshooting.md).

---

## Windows installer path

The offline installer bundles **Python 3.12**, **MySQL 8** (as a Windows service when needed), and **WinSW**. It creates a production `.env`, registers **mlamehticketApp** as an auto-start service (Daphne), and supports **fresh**, **repair**, and **in-place upgrade** modes.

### SmartScreen (unsigned EXE)

The Setup EXE is **not code-signed**. On first run Windows may show **“Windows protected your PC”**:

1. Click **More info**.
2. Click **Run anyway**.

Verify the download with the published SHA256:

```powershell
Get-FileHash .\mlamehticketSetup.exe -Algorithm SHA256
# Compare to the contents of mlamehticketSetup.exe.sha256
```

On domain-joined PCs, a self-signed publisher certificate deployed via Group Policy can remove the prompt.

### Build the installer (developers)

1. Install **Inno Setup 6** on the build machine.
2. Ensure a project venv exists (`.\test-local.ps1 -InstallDeps`).
3. Download offline binaries (internet required once):

```powershell
.\installer\fetch-payload.ps1
```

4. Build:

```powershell
.\installer\build.ps1
```

Output:

```text
installer\Output\mlamehticketSetup.exe
installer\Output\mlamehticketSetup.exe.sha256
```

See also [installer/README.md](../../installer/README.md).

### Install on a client machine

1. Run `mlamehticketSetup.exe` **as Administrator**.
2. Choose the install folder (default `C:\mlamehticket`). Paths must be ASCII, on a local fixed drive.
3. On a **fresh** install, set **server address**, **port**, and **admin email**.
4. If an existing MySQL/MariaDB is detected, enter admin credentials (or choose a private bundled instance).
5. Setup installs Python/MySQL only when missing, generates `.env`, creates the database/user, runs migrations, and starts the **mlamehticketApp** service.
6. Open **`FIRST-LOGIN.txt`** in the install folder for admin and database passwords (Administrators ACL). Change the admin password on first login.

The app listens on the port you chose (default **8000**). Shortcuts open the browser; they no longer start the server manually.

### Upgrade / repair

| Situation | Behavior |
|-----------|----------|
| Newer Setup EXE | **Upgrade**: stops service, archives code + `backup_db`, replaces files (preserves `.env`, media, backups, logs, mysqldata, `*.pem`), migrates, restarts |
| Same version again | **Repair**: re-checks Python/MySQL/venv/service/migrations; does not rewrite `.env` or data |
| Older Setup EXE | **Blocked** (downgrade not supported) |

Bump the root `VERSION` file before building a release you intend to roll out.

### Failed upgrade — manual restore

Pre-upgrade always writes artifacts under `{install}\backups\` before replacing files. If Setup reports failure (or `install.ps1` exits non-zero), restore manually:

```powershell
# Stop the app service
Stop-Service mlamehticketApp -ErrorAction SilentlyContinue

# Restore database (use credentials from .env; mysql.exe is on PATH or under mysql\bin)
$env:MYSQL_PWD = "<DB_PASSWORD from .env>"
Get-Content .\backups\backup_YYYY-MM-DD_HHMMSS.sql | & .\mysql\bin\mysql.exe -u mlamehticket_user -h 127.0.0.1 mlamehticket
Remove-Item Env:\MYSQL_PWD

# Restore code from the pre-upgrade zip (overwrite app files; keep .env, media, mysqldata, backups, logs)
Expand-Archive -Path .\backups\code-<oldversion>.zip -DestinationPath .\ -Force

# Restart
Start-Service mlamehticketApp
```

Exact dump and zip names are listed in `backups\preupgrade-<oldversion>.txt` (when present) or are the newest `backup_*.sql` / `code-*.zip` under `backups\`.

### Logs

All under `{install}\logs\`:

| File | Contents |
|------|----------|
| `app.log` | Django / application (daily rotation, 30 days) |
| `mlamehticketApp_YYYYMMDD.out.log` / `.err.log` | Daphne stdout/stderr (WinSW `roll-by-time`; date is part of the filename) |
| `mysql-error.log` | Bundled MySQL error log |
| `install-*.log` | Installer transcripts |

### Notes

- **Payload stays on disk.** The ~300 MB `installer\payload\` folder (embeddable Python ZIP, VC++ redist, get-pip, MySQL ZIP, WinSW) remains after install on purpose so **repair** can reprovision without the original Setup EXE.
- **Private Python** is the official **embeddable ZIP** extracted to `{install}\python` (not the full Windows EXE installer). `VC_redist.x64.exe` is installed first so `python.exe` can run on a clean machine.
- **Install transcripts** live under `%ProgramData%\mlamehticket\logs\` so they survive if the install folder is wiped. `{install}\logs\` may only contain a pointer file for the transcript.
- **Prefer the private Python.** If a system Python 3.12+ is already present, the installer may reuse it for the `.venv`. Uninstalling or upgrading that system Python later can break the service.
- **Network on first install:** `get-pip` and `pip install -r requirements.txt` need internet unless you pre-seed a wheelhouse.

### Uninstall

Use **Add or Remove Programs** or the Start Menu uninstaller. You will be asked whether to delete data (`mysqldata`, `media`, `backups`, `logs`, `.env`). Services, firewall rule, and installer-created trees (`.venv`, private Python/MySQL, etc.) are removed.

---

## First login and bootstrap admin

There is **no** `bootstrap_superadmin` management command.

The default superuser is created by a **`post_migrate`** signal (`accounts/signals.py`) when **all** of the following hold:

1. `DEFAULT_SUPERADMIN_PASSWORD` is set in the environment / `.env`.
2. The password is **not** considered weak. Weak values (case-insensitive after strip) are skipped:
   - empty string `""`
   - `admin`
   - `password`
   - `changeme`
   - `12345678`
3. No user with `DEFAULT_SUPERADMIN_USERNAME` (default `admin`) already exists.

Optional related env vars (with defaults):

| Variable | Default |
|----------|---------|
| `DEFAULT_SUPERADMIN_USERNAME` | `admin` |
| `DEFAULT_SUPERADMIN_EMAIL` | `admin@mlamehticket.local` |
| `DEFAULT_SUPERADMIN_PASSWORD` | empty (skip create) |

New bootstrap admins are created with **`requires_password_change=True`**. On first login the app forces a password change before normal use.

When **`DEBUG=0`**, Django will not start if `DEFAULT_SUPERADMIN_PASSWORD` is missing or weak (`ImproperlyConfigured`). Set a strong password in `.env`, then run:

```powershell
python manage.py migrate
```

After bootstrap, change the password immediately and treat `.env` as a secret. See [Security hardening](security-hardening.md).

---

## Verify the install

1. Open `http://localhost:8000` (or the LAN IP if bound to `0.0.0.0`).
2. Sign in with the bootstrap username/password (or demo users if you seeded).
3. Complete the forced password change if prompted.
4. Configure SMTP under **Settings → Email** (database `EmailSetting` — not `.env`). Gmail helpers: [Gmail app password](../admin-guide/gmail-app-password.md).
5. Confirm `SITE_URL` matches how users reach the app so email links work.

If something fails, see [Troubleshooting](troubleshooting.md).

---

## Related documentation

| Topic | Doc |
|-------|-----|
| Every `.env` variable | [Configuration](configuration.md) |
| MySQL + Daphne production | [Deployment](deployment.md) |
| Backups and restore | [Backup and restore](backup-restore.md) |
| Production checklist | [Security hardening](security-hardening.md) |
| Common failures | [Troubleshooting](troubleshooting.md) |
