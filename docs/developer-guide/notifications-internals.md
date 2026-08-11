# Notifications internals

How in-app notifications, WebSocket push, web push, and SMTP email are orchestrated without Celery.

**Audience:** Developers changing notification recipients, copy, email templates, or webpush behavior.

## Pipeline overview

Most ticket/announcement events call a function in `notifications.services`. That function:

1. Resolves **recipient users**.
2. Builds bilingual title/body via `bilingual(...)` / `gettext_noop` strings.
3. Creates `InAppNotification` rows (with 60s dedupe for non-message types).
4. Broadcasts each row on Channels to `user_{id}_notifications`.
5. Attempts **web push** via patched `django-webpush` helpers.
6. **Enqueues** an email job on the in-process queue (does not send SMTP inline).

Email preference flags on the active `EmailSetting` gate **email only**. In-app and web push still run when those flags are off.

## Entry points (`notifications.services`)

| Function | Typical trigger |
|---|---|
| `notify_new_ticket` | Ticket created (signal) |
| `notify_ticket_picked` | Pick action |
| `notify_ticket_update` | Message / status / general update |
| `notify_transfer_requested` | Transfer requested |
| `notify_transfer_accepted` | Transfer accepted |
| `notify_transfer_denied` | Transfer denied |
| `notify_announcement_created` | Announcement created |

Helpers:

- `_notify_users` — create + WS + webpush
- `_broadcast_notification` — Channels `group_send`
- `_enqueue` — wraps `enqueue_email` with logging
- `_get_admin_users` — active superusers or role name `admin`
- `_unique_users` — de-dupe across querysets / extras

## Recipient rules

Branch and department querysets come from `notifications.utils`:

- `get_branch_users(ticket)` — active branch users on the ticket’s branch; excludes superusers and role name `admin`
- `get_department_users(ticket)` — active support users on the ticket’s department; same exclusions

Admins are added separately via `_get_admin_users()`.

| Event | Recipients (then exclude actor where noted) |
|---|---|
| New ticket | Branch users + department users + admins; exclude creator |
| Ticket picked | Same audience; exclude actor |
| Status change | Same audience; exclude actor |
| Ticket update (non-message) | Same audience; exclude actor |
| Message (assigned ticket) | Creator + assignee + admins; exclude actor |
| Message (unassigned, first message) | Branch + department + creator + admins; exclude actor |
| Message (unassigned, later) | Creator + admins; exclude actor |
| Transfer requested | Target assignee only |
| Transfer accepted / denied | Original requester only |
| Announcement (no branch) | All active users; exclude actor |
| Announcement (target branch) | That branch’s users **or** superusers; support agents outside the branch are skipped |

Message notification type skips the 60-second title/link dedupe window used for other types.

## In-app model fields

English `title` / `message` are required for dedupe, web push payload, and UI fallback. Arabic `title_ar` / `message_ar` are stored in parallel (and mirrored into `params` for compatibility). The panel prefers Arabic columns when present.

See [data-model.md](data-model.md) for the full field list.

## Email queue (`notifications.email_queue`)

Not Celery. Design:

- Module-level `queue.Queue` of `EmailJob` dataclasses.
- `enqueue_email(func, *args, max_attempts=…, retry_delay=…, delay_seconds=…, **kwargs)` starts a **daemon** thread named `email-worker` on first use.
- Worker calls `close_old_connections()` before/after each job (important under MySQL `CONN_MAX_AGE`).
- Failures retry up to `max_attempts`; optional `delay_seconds` schedules put via `threading.Timer`.

Message-related ticket update emails often use `delay_seconds=120` so an already-read in-app notice can suppress redundant mail noise downstream.

Jobs live in `notifications.email_jobs` (for example `send_new_ticket_email`, `send_ticket_picked_email`, `send_ticket_update_email`, `send_transfer_event_email`, `send_announcement_email`) and render through the email content/template helpers against `EmailSetting` / `EmailTemplate`.

## Web push patches (`notifications.apps.NotificationsConfig.ready`)

`django-webpush` is customized at startup:

1. **Strip `user_agent` from `SubscriptionInfo` local fields** so the project’s migration that dropped the column stays compatible with the library model metadata.
2. **Replace `webpush.forms` in `sys.modules`** with forms that:
   - Omit `user_agent` from subscription fields (`endpoint`, `auth`, `p256dh`, `browser`).
   - Allow multiple devices; only remove duplicate `PushInformation` rows for the same user **and** same endpoint.
3. **Wrap send helpers** (`send_notification_to_user` / `send_notification_to_group` and package aliases) so per-subscription failures are logged, and 403/404/410 responses delete dead subscriptions instead of aborting the whole loop.

Services call `webpush.send_user_notification(...)` with a JSON payload (`title`/`body`/`icon`/`data.url`).

## WebSocket delivery

After create, `_broadcast_notification` sends to `user_{recipient_id}_notifications` with `type: notification.event`. See [realtime.md](realtime.md).

HTTP APIs under `/notifications/` load, mark read, delete, and clear notifications for the bell UI (`notifications.views`).

## Operational notes

- Email requires an **active** `EmailSetting` and working SMTP; missing config fails soft inside jobs.
- In-process queue jobs are lost if the Daphne process dies mid-flight — acceptable for this deployment model, not a durable broker.
- Multi-process deploys need either sticky single-worker realtime or a shared channel layer; email workers also do not share a queue across processes.

## Related docs

- [Architecture](architecture.md)
- [Realtime](realtime.md)
- [Data model](data-model.md)
- [URL reference](url-reference.md)
