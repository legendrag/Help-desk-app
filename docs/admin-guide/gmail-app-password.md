# Gmail app password setup

**Audience:** Administrators configuring outbound email for notifications.

Use a Google App Password (not your normal Gmail password) as the SMTP credential in **Settings Hub → Email Settings**.

SMTP is stored in the database (`core.EmailSetting`), not in `.env`.

## Prerequisites

- A Google account with **2-Step Verification** enabled.
- A role with **Manage Email Settings** (`can_manage_email`), or a superuser account.

## Create the app password

1. Sign in to the Gmail account that will send notifications.
2. Open [Google Account → Security](https://myaccount.google.com/security).
3. Confirm **2-Step Verification** is on.
4. Open **App passwords** (search for it if the link is hidden).
5. Create a new app password (Google shows a 16-character password).
6. Copy it once — Google will not show it again.

## Configure Email Settings in the app

1. Open **Settings Hub** (sidebar) → **Email Settings** tab.
2. Add a new SMTP row (or edit the existing one) with:

| Field | Value |
|---|---|
| SMTP Host | `smtp.gmail.com` |
| SMTP Port | `587` |
| Encryption | `tls` |
| SMTP Email | your Gmail address |
| SMTP Password | the 16-character app password |
| From Name / From Email | sender identity shown to recipients |

3. Mark the row as **active**. Only one Email Setting can be active at a time; saving an active row deactivates others.
4. Enable the notification event toggles you want (new tickets, picked, messages, status, updates, announcements).
5. Optionally customize subjects/bodies under email templates, then use **Send test** for an event type.

Also set `SITE_URL` in `.env` (no trailing slash) so email links are absolute, for example `https://helpdesk.example.com` or `http://192.168.1.10:8000`.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Authentication failed | App password is correct; 2-Step Verification is enabled; you did not paste the normal account password |
| Connection timeout | Firewall allows outbound TCP to `smtp.gmail.com:587` |
| No emails arrive | Active Email Setting exists; the event toggle is on; `SITE_URL` is set; check server logs for retry errors from the in-process email queue |
| Links in email are relative | `SITE_URL` is empty or wrong in `.env` |

For the full email settings and template reference, see [Email settings](email-settings.md).
