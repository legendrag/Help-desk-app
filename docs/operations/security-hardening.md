# Security hardening

Production security checklist for mlamehticket operators.

**Audience:** Operators locking down a live instance before and after go-live.

---

## Quick checklist

| Item | Production expectation |
|------|------------------------|
| `DEBUG` | `0` |
| `SECRET_KEY` | Long, unique, random — never the example value |
| `ALLOWED_HOSTS` | Explicit hosts/IPs — not `*` |
| `CSRF_TRUSTED_ORIGINS` | Full origins (`https://…` or `http://host:8000`) for every public URL |
| `DEFAULT_SUPERADMIN_PASSWORD` | Strong; change password on first login |
| `.env` | Restricted filesystem permissions; never in git |
| `private_key.pem` / VAPID private material | Treated as a secret; backed up securely |
| Channel layer | Know that **InMemoryChannelLayer** is per-process |
| Sessions | Understand `SESSION_COOKIE_AGE` (default 3 days) |
| Attachments | Enforce size/extension limits already in settings |

Related: [Configuration](configuration.md) · [Deployment](deployment.md) · [Backup and restore](backup-restore.md) · [Troubleshooting](troubleshooting.md)

---

## Debug mode

```env
DEBUG=0
```

With `DEBUG=1`, Django may expose stack traces, settings hints, and development media serving. Always ship with debug off.

---

## Secret key

```env
SECRET_KEY=...
```

Used for cryptographic signing (sessions, CSRF tokens, etc.). Generate a fresh long random string per environment. Rotating it invalidates existing sessions — plan for brief re-logins if you must rotate.

Never commit `SECRET_KEY` to version control.

---

## Hosts and CSRF

```env
ALLOWED_HOSTS=helpdesk.example.com,192.168.1.10
CSRF_TRUSTED_ORIGINS=https://helpdesk.example.com,http://192.168.1.10:8000
```

- **`ALLOWED_HOSTS=*`** is acceptable only for local experiments. In production it weakens Host-header protections.
- Include every name or IP clients use in the browser.
- **`CSRF_TRUSTED_ORIGINS`** must include the scheme and port when non-default. Missing entries cause POST failures (login, forms, HTMX actions) that look like “CSRF verification failed.”

---

## Bootstrap admin password

There is **no** `bootstrap_superadmin` management command. Creation happens in `accounts/signals.py` on `post_migrate` when `DEFAULT_SUPERADMIN_PASSWORD` is set and not weak.

Weak values (skipped; and when `DEBUG=0`, Django raises `ImproperlyConfigured`):

- empty
- `admin`
- `password`
- `changeme`
- `12345678`

New bootstrap users get **`requires_password_change=True`**. Require that first login change immediately, then clear or rotate the bootstrap password in `.env` so it is not a standing backdoor if the file leaks.

Prefer unique usernames in hostile environments rather than leaving the default `admin` forever.

---

## Treat these as secrets

| Asset | Why |
|-------|-----|
| `.env` | `SECRET_KEY`, DB password, bootstrap password, optional VAPID material |
| Database dumps from `backup_db` | Full PII and password hashes |
| `private_key.pem` (or `VAPID_PRIVATE_KEY`) | Web Push authenticity; losing/replacing it breaks existing push subscriptions |
| Media zip exports | May contain confidential attachments |

Restrict NTFS/ACLs, keep off shared drives without encryption, and exclude from backups that land in public cloud buckets without access control. See [Backup and restore](backup-restore.md).

SMTP credentials live in the **`EmailSetting`** database table — protect DB access the same way you protect `.env`.

---

## Channel layer: InMemoryChannelLayer

Default setting:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
```

Implications:

- Realtime messages stay **inside one process**.
- Running **multiple Daphne/worker processes** (or multiple machines) **will not** share WebSocket/channel events unless you replace this with a shared backend (for example Redis channel layer).
- The stock stack intentionally has **no Redis/Celery**. For a single Daphne process on a LAN server this is usually fine; scale-out requires architectural change.

Do not assume horizontal scaling “just works” with the default channel layer.

---

## Sessions

```env
SESSION_COOKIE_AGE=259200
```

Default **259200 seconds (3 days)**. Sessions are saved on every request (`SESSION_SAVE_EVERY_REQUEST`), so active users keep sliding renewal. They do not expire solely because the browser closed.

Shorten this value for higher-security environments; balance against help-desk usability (agents stay logged in across shifts).

Login forms also rate-limit failed attempts (**5 failures / 5 minutes** per username). See [Troubleshooting](troubleshooting.md) for lockout behavior.

---

## Attachment limits

Configured in code (`config/settings.py`), not via `.env`:

| Control | Value |
|---------|--------|
| Maximum upload size | **10 MiB** (`MAX_ATTACHMENT_SIZE`) |
| Allowed extensions | `.pdf`, `.docx`, `.xlsx`, `.jpg`, `.jpeg`, `.png` |

Reject unexpected types and oversized files at the application layer. Still scan media storage and backups for sensitive content under your org policy.

---

## Network and process hygiene

- Prefer binding production behind a reverse proxy with TLS when the app is internet-facing; for internal LAN, still restrict who can reach port **8000**.
- Run under a least-privilege Windows/Linux service account when possible.
- Keep Python and MySQL patched.
- Use Daphne (`run-mlamehticket.ps1`) rather than exposing `runserver`.
- After deploy, verify `DEBUG` is off by confirming you do not get Django debug pages on intentional 404s.

---

## Media in production

Django’s URLConf only mounts `MEDIA_URL` when `DEBUG` is true. WhiteNoise serves **static** files from `STATIC_ROOT`, not user uploads. Plan how `/media/` is served in production (reverse proxy alias to `MEDIA_ROOT`, or another controlled mechanism). Leaving `DEBUG=1` solely to serve media is **not** an acceptable hardening trade-off. See [Troubleshooting](troubleshooting.md).

---

## After hardening

1. Restart Daphne so env changes apply.
2. Log in, change bootstrap password, create named admin accounts, disable unused ones.
3. Confirm CSRF and host settings with a real browser POST.
4. Schedule encrypted or access-controlled off-site backups.
5. Document who can read `.env` and restore dumps.
