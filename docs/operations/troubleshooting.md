# Troubleshooting

Practical fixes for common mlamehticket operations issues.

**Audience:** Operators and developers diagnosing a running or newly installed instance.

---

## Quick lookup

| Symptom | Likely cause | Where to look |
|---------|--------------|---------------|
| Email never arrives | SMTP not configured / wrong `SITE_URL` / event flags off | [Email not sending](#email-not-sending) |
| Browser push missing | VAPID keys / permission / HTTPS or secure context | [Push not arriving](#push-notifications-not-arriving) |
| Chat drops / no live updates | Using `runserver` / channel layer / proxy timeouts | [WebSocket disconnects](#websocket-disconnects) |
| Arabic mojibake in DB | Database not utf8mb4 | [MySQL charset](#mysql-charset-and-garbled-text) |
| UI stays English when Arabic selected | `.mo` not compiled / catalog drift | [Arabic showing as English](#arabic-showing-as-english) |
| “Too many failed login attempts” | Rate limit (5 / 5 minutes) | [Login lockout](#login-lockout) |
| Attachment or image URLs 404 in production | Media only auto-mounted when `DEBUG=1` | [Media 404 in production](#media-404-in-production) |
| Realtime broken after “prod” start | Started `runserver` instead of Daphne | [Daphne vs runserver](#daphne-vs-runserver-mistakes) |

Related: [Configuration](configuration.md) · [Deployment](deployment.md) · [Installation](installation.md) · [Security hardening](security-hardening.md)

---

## Email not sending

SMTP is **not** read from `.env`. It lives in the database as **`EmailSetting`**.

Checklist:

1. **Settings → Email** — an active `EmailSetting` exists with correct host, port, TLS/SSL, username, password, and from-address.
2. Event toggles on that setting allow the notification type you expect (email flags do not disable in-app or Web Push).
3. **`SITE_URL`** is set to the reachable base URL **without** relying on a trailing slash (e.g. `http://192.168.1.10:8000`). Wrong/empty `SITE_URL` does not always block send, but produces useless relative links in the message body.
4. Provider-specific auth — Gmail often needs an [app password](../admin-guide/gmail-app-password.md), not the normal account password.
5. Firewall / ISP blocks on outbound port 465/587.
6. Check **`{install}\logs\app.log`** (Windows service) or the process console (manual Daphne / `runserver`) for SMTP exceptions when triggering a notification.

Test with a known event (new ticket, assignment) after saving settings. Restart is usually unnecessary for DB-stored SMTP, but restart Daphne if you also changed `.env`.

---

## Push notifications not arriving

Web Push depends on VAPID keys and browser permission.

Checklist:

1. User granted notification permission for the site origin.
2. Service worker (`/sw.js`) loads without errors (browser DevTools → Application).
3. VAPID keys exist — env `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`, or auto-generated `private_key.pem` under the project root. If you wiped the key file after users subscribed, existing subscriptions become invalid; regenerate only if you accept re-subscribing clients.
4. `VAPID_ADMIN_EMAIL` is set to a plausible contact address.
5. Secure context: many browsers require **HTTPS** (or `localhost`) for push. Plain `http://LAN-IP` may block or limit push.
6. Distinguish **in-app** notifications (bell) from **Web Push** (OS/browser). Email flags do not control push.

---

## WebSocket disconnects

Live chat and some notification delivery use Django Channels over WebSockets.

Checklist:

1. Confirm the server is **Daphne** (`run-mlamehticket.ps1` or `daphne -b 0.0.0.0 -p 8000 config.asgi:application`), not `runserver`.
2. Browser DevTools → Network → WS — connection should stay `101` / open; note close codes.
3. Reverse proxies (nginx, IIS ARR) must allow WebSocket upgrade and not idle-timeout too aggressively.
4. Default **`InMemoryChannelLayer`** is per-process. Multiple workers/processes do not share events — stick to one Daphne process or introduce a shared channel layer (not bundled by default).
5. Laptop sleep, Wi-Fi roam, or VPN blips drop sockets; the client should reconnect — if not, hard-refresh and retest on a stable LAN.

---

## MySQL charset and garbled text

Create the database explicitly:

```sql
CREATE DATABASE mlamehticket CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

If the schema was created as `utf8` (3-byte) or `latin1`, Arabic (and some symbols) can corrupt on write. Fixing later may require dump/reimport with correct charset and careful conversion — easier to create utf8mb4 from day one.

Also ensure the MySQL connection and client tools use utf8mb4. Application settings expect MySQL via `DB_ENGINE=mysql` and PyMySQL — see [Deployment](deployment.md).

---

## Arabic showing as English

UI language is cookie-based (no URL language prefix). If the UI stays English after choosing Arabic:

1. Confirm the language cookie/switcher actually toggles (hard refresh).
2. Compile gettext catalogs:

```powershell
.\.venv\Scripts\python.exe scripts\i18n.py compile
```

3. If strings are missing from the catalog:

```powershell
.\.venv\Scripts\python.exe scripts\i18n.py update
# translate new entries in locale/ar/LC_MESSAGES/django.po
.\.venv\Scripts\python.exe scripts\i18n.py compile
.\.venv\Scripts\python.exe scripts\i18n.py check
```

4. `test-local.ps1` runs this check by default; `-SkipI18nCheck` bypasses it and can hide missing translations.
5. Restart the server after replacing `.mo` files if the process cached old catalogs.

Untranslated or uncompiled entries fall back to English — that is expected gettext behavior, not a browser bug.

---

## Login lockout

Failed logins are rate-limited in `CustomAuthenticationForm`:

- **5** failed attempts per username
- Lockout window: **5 minutes** (`300` seconds)
- Message: “Too many failed login attempts. Please try again in 5 minutes.”

Counters live in Django’s **cache** (default local memory cache unless you configured otherwise). Waiting out the window clears the block; restarting the app process often clears in-memory cache too (useful on a single-dev machine, not a security bypass to rely on in production).

Successful login clears the counter for that username. Inactive accounts show a separate inactive-account error.

Bootstrap accounts may also force **password change** (`requires_password_change`) — that is not a lockout; complete the password form to proceed.

---

## Media 404 in production

With `DEBUG=0`, `config/urls.py` does **not** add Django’s static-media helper for `MEDIA_URL`. WhiteNoise serves **`STATIC_ROOT`** (CSS/JS/images collected by `collectstatic`), **not** user uploads under `MEDIA_ROOT`.

Symptoms: ticket attachments and KB files return **404** while the rest of the site works.

Mitigations:

1. Serve `/media/` from a reverse proxy (nginx, IIS, Caddy) pointing at the project `media/` directory.
2. Or another controlled ASGI/static mapping you maintain — do **not** turn `DEBUG=1` in production just to serve uploads.
3. Confirm files exist on disk under `media/` and that restore/unzip put them in the expected tree ([Backup and restore](backup-restore.md)).
4. After `cleanup_media --delete`, intentionally removed orphans will 404 — expected.

---

## Daphne vs runserver mistakes

| Goal | Correct | Incorrect |
|------|---------|-----------|
| Local SQLite UI testing | `.\test-local.ps1` or `runserver` | Expecting production WebSocket behavior |
| Production / LAN with chat | `.\run-mlamehticket.ps1` or Daphne on `0.0.0.0:8000` | `python manage.py runserver` on a customer server |
| Installer client site | Desktop shortcut → Daphne launcher | Starting the wrong Python without venv |

Common mistakes:

- Editing `.env` but not restarting Daphne — process still has old env (`run-mlamehticket.ps1` loads `.env` at start).
- Binding only to `127.0.0.1` then wondering why LAN clients cannot connect — use `0.0.0.0` as the launcher does.
- Forgetting Windows Firewall port **8000**.
- Using `ALLOWED_HOSTS=*` or omitting the LAN IP while testing host validation with `DEBUG=0`.
- Assuming multiple Daphne workers share chat state — they do not with `InMemoryChannelLayer`.

---

## Database and migrate issues

| Problem | What to try |
|---------|-------------|
| `ImproperlyConfigured` about `DEFAULT_SUPERADMIN_PASSWORD` | Set a strong password in `.env` when `DEBUG=0`; weak list includes empty, `admin`, `password`, `changeme`, `12345678` |
| No admin user after migrate | Password was empty/weak so bootstrap was skipped; set password and migrate again (or create a superuser once you have shell access) |
| Looking for `bootstrap_superadmin` | Command does not exist — use env + `migrate` |
| MySQL connection refused | Service running? `DB_HOST`/`DB_PORT`/`DB_PASSWORD`? User grants on `mlamehticket`? |
| `backup_db` rejects `--dir` | Directory must resolve **inside** the project root |
| `mysqldump` not found | Install MySQL client tools and ensure they are on `PATH` |

---

## Static files missing

```powershell
python manage.py collectstatic --noinput
```

Restart Daphne. WhiteNoise serves collected files from `staticfiles/`. If CSS is missing only in production, you likely skipped `collectstatic` after deploy or are not running through the ASGI app that loads WhiteNoise middleware.

---

## Still stuck?

1. Reproduce with browser DevTools (Network, Console, WS) open.
2. Watch the Daphne/runserver console for tracebacks.
3. Verify `.env` values against [Configuration](configuration.md).
4. Confirm you followed [Deployment](deployment.md) for MySQL + Daphne.
5. For data loss scenarios, use [Backup and restore](backup-restore.md) on a **copy** of the dump first.
