# Email settings

Configure SMTP, notification toggles, and per-event email templates so the help desk can send outbound mail.

**Audience:** Administrators with **Manage Email Settings** (`can_manage_email`), or a Django superuser. Viewing the Email Settings tab still requires **Access Settings**.

## Where settings live

SMTP credentials and notification toggles are stored in the database (`core.EmailSetting`), **not** in `.env`.

You still need `SITE_URL` in `.env` (no trailing slash) so links in emails are absolute, for example:

```text
SITE_URL=https://helpdesk.example.com
```

or for local testing:

```text
SITE_URL=http://192.168.1.10:8000
```

Open [Settings Hub](settings-hub.md) → **Email Settings**.

For Gmail specifically, follow [Gmail app password](gmail-app-password.md) — use a Google App Password, not the normal account password.

## Permissions

| Action | Requirement |
|---|---|
| Open Settings Hub / see Email Settings tab | Access Settings (or superuser) |
| Create, edit, delete SMTP rows | Manage Email Settings |
| Edit templates / send test | Manage Email Settings |

## SMTP configuration

| Field | Purpose |
|---|---|
| SMTP Host | Mail server hostname (for example `smtp.gmail.com`) |
| SMTP Port | Usually `587` (TLS) or `465` (SSL) |
| Encryption | `none`, `tls`, or `ssl` |
| SMTP Email | Auth username / mailbox |
| SMTP Password | Auth secret (app password for Gmail) |
| From Name | Display name on outgoing mail |
| From Email | Envelope / From address shown to recipients |
| Active | Whether this row is the live configuration |

### Only one active setting

At most one Email Setting may have **Active** (`is_active`) at a time (database unique constraint). Saving a row as active deactivates others. The mailer loads the active row when sending.

Keep inactive rows for staging or fallback credentials if you like, but only the active row is used.

## Notification toggles

On the active Email Setting, enable or disable whole event groups:

| Field | UI label | Typical use |
|---|---|---|
| `notify_new_ticket` | New tickets | New ticket created |
| `notify_ticket_picked` | Ticket picked | Agent picks / accepts a ticket |
| `notify_ticket_message` | Ticket messages | New chat reply |
| `notify_ticket_status` | Status changes | Status updates |
| `notify_ticket_update` | Ticket updates | Other ticket field updates |
| `notify_announcement` | Announcements | News / announcement posts |

If a toggle is off, email for that group is not sent even when a template exists. In-app notifications may still fire separately — see [Notifications](../user-guide/notifications.md).

Transfer-related emails use their own template event types (`transfer_requested`, `transfer_accepted`, `transfer_denied`). They ride on the ticket notification pipeline; ensure SMTP is active and templates are configured for those events.

## Email templates

Templates are stored per event type (`core.EmailTemplate`). Each event has one subject and one plain-text body. Merge fields use `{{ token }}` syntax (spaces inside the braces are allowed).

### Event types

| Event type (system) | UI label |
|---|---|
| `new_ticket` | New ticket |
| `ticket_picked` | Ticket picked |
| `ticket_message` | Ticket reply |
| `ticket_status` | Status change |
| `ticket_update` | Ticket update |
| `transfer_requested` | Transfer requested |
| `transfer_accepted` | Transfer accepted |
| `transfer_denied` | Transfer declined |
| `announcement` | Announcement |

The Settings UI shows insert buttons for the merge fields allowed for the selected event. Unknown tokens render as empty strings.

### Default subject / body patterns

Defaults (seeded if missing) look like:

```text
[{{ brand_name }}] New ticket #{{ ticket_number }}: {{ title }}
```

Bodies are plain text with short narrative lines plus `{{ description }}` or `{{ message }}` / `{{ content }}` as appropriate. Customize freely; keep tokens spelled exactly as listed below.

### Merge fields by event

#### `new_ticket`

`brand_name`, `ticket_number`, `title`, `requester`, `department`, `branch`, `priority`, `status`, `description`, `ticket_url`

#### `ticket_picked`

`brand_name`, `ticket_number`, `title`, `actor`, `status`, `assignee`, `description`, `ticket_url`

#### `ticket_message`

`brand_name`, `ticket_number`, `title`, `actor`, `message`, `ticket_url`

#### `ticket_status`

`brand_name`, `ticket_number`, `title`, `actor`, `status`, `description`, `ticket_url`

#### `ticket_update`

`brand_name`, `ticket_number`, `title`, `actor`, `status`, `description`, `ticket_url`

#### `transfer_requested` / `transfer_accepted` / `transfer_denied`

`brand_name`, `ticket_number`, `title`, `actor`, `description`, `ticket_url`

#### `announcement`

`brand_name`, `title`, `content`, `audience`, `expires`, `posted_by`, `announcement_url`

### Token meaning (overview)

| Token | Typical value |
|---|---|
| `brand_name` | Product brand string (for example MlamehTicket) |
| `ticket_number` | Ticket number |
| `title` | Ticket or announcement title (may be truncated) |
| `requester` | Display name of ticket creator |
| `assignee` | Display name of assigned agent |
| `actor` | User who triggered the event |
| `department` / `branch` | Org names |
| `priority` / `status` | Human-readable labels |
| `description` | Ticket description (truncated) |
| `message` | Chat message body (truncated) |
| `content` | Announcement body |
| `ticket_url` | Absolute ticket link (needs `SITE_URL`) |
| `announcement_url` | Absolute announcements link |
| `audience` / `expires` / `posted_by` | Announcement metadata |

Example snippet:

```text
Hello,

{{ actor }} updated ticket #{{ ticket_number }} to {{ status }}.

Open it here: {{ ticket_url }}
```

## Send test

The Email Settings UI includes a **Send test** action for a selected event type. Use it after changing SMTP or templates.

Prerequisites for a successful test:

1. An **active** Email Setting with working SMTP credentials.
2. Correct encryption/port for your provider.
3. `SITE_URL` set if you care about link correctness in the sample.
4. **Manage Email Settings** on your role (or superuser).

## Operational checklist

1. Set `SITE_URL` in `.env` and restart the app process if needed.
2. Add SMTP credentials; mark the row **Active**.
3. Enable the notification toggles you want in production.
4. Review each event template and merge tokens.
5. Send a test for `new_ticket` (and any other critical events).
6. For Gmail, complete [Gmail app password](gmail-app-password.md).

## Troubleshooting

| Symptom | What to check |
|---|---|
| No mail at all | Active Email Setting exists; SMTP host/port/encryption; firewall egress |
| Auth failures (Gmail) | App password + 2-Step Verification — see [Gmail app password](gmail-app-password.md) |
| Some events silent | Matching notify_* toggle is off |
| Broken or relative links | `SITE_URL` empty, wrong, or has a trailing slash |
| Template looks wrong | Token spelling; event-specific merge field list; empty DB subject/body falls back to defaults |

Outbound mail is processed by the app's in-process email queue. Check application logs if tests fail after SMTP looks correct.

## Related docs

- [Gmail app password](gmail-app-password.md)
- [Settings Hub](settings-hub.md)
- [Users and roles](users-and-roles.md)
- [Notifications](../user-guide/notifications.md)
- [Announcements](../user-guide/announcements.md)
- [Transfer and merge](../user-guide/transfer-and-merge.md)
- [Configuration](../operations/configuration.md)
