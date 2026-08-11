# URL reference

Named HTTP routes by app prefix, plus WebSocket routes from ASGI.

**Audience:** Developers wiring views, templates (`{% url %}`), HTMX targets, or clients.

## Root (`config/urls.py`)

| Method / path | Name | Notes |
|---|---|---|
| `GET /` | `root` | Redirects to `tickets_list` |
| `GET /admin/` | — | Django admin |
| `GET/POST /i18n/` | — | `django.conf.urls.i18n` (language cookie) |
| `GET /sw.js` | `sw.js` | Service worker template, never-cached |
| `/webpush/` | — | `django-webpush` URLs |
| `GET /favicon.ico` | — | Redirect to static favicon |

Media is served by Django only when `DEBUG` is true.

## Accounts — `/accounts/`

| Path | Name |
|---|---|
| `login/` | `login` |
| `logout/` | `logout` |
| `password-change/` | `password_change` |
| `users/` | `user_list` |
| `users/add/` | `user_create` |
| `users/<int:pk>/edit/` | `user_update` |
| `users/<int:pk>/delete/` | `user_delete` |
| `auth-check/` | `auth_check` |

`auth_check` returns JSON `{ "authenticated": bool }`.

## Core — `/core/`

### Organization CRUD

| Path | Name |
|---|---|
| `branches/` | `branch_list` |
| `branches/add/` | `branch_create` |
| `branches/<int:pk>/edit/` | `branch_update` |
| `branches/<int:pk>/delete/` | `branch_delete` |
| `departments/` | `department_list` |
| `departments/add/` | `department_create` |
| `departments/<int:pk>/edit/` | `department_update` |
| `departments/<int:pk>/delete/` | `department_delete` |
| `categories/` | `category_list` |
| `categories/add/` | `category_create` |
| `categories/<int:pk>/edit/` | `category_update` |
| `categories/<int:pk>/delete/` | `category_delete` |
| `roles/` | `role_list` |
| `roles/add/` | `role_create` |
| `roles/<int:pk>/edit/` | `role_update` |
| `roles/<int:pk>/delete/` | `role_delete` |

These `category_*` routes manage **`core.Category`** (ticket categories), not KB categories.

### Email

| Path | Name |
|---|---|
| `email-settings/` | `email_setting_list` |
| `email-settings/add/` | `email_setting_create` |
| `email-settings/<int:pk>/edit/` | `email_setting_update` |
| `email-settings/<int:pk>/delete/` | `email_setting_delete` |
| `email-templates/form/` | `email_template_form` |
| `email-templates/<str:event_type>/save/` | `email_template_save` |
| `email-templates/<str:event_type>/test/` | `email_template_test` |

### Maintenance

| Path | Name |
|---|---|
| `maintenance/` | `maintenance` |
| `maintenance/export/tickets/` | `export_tickets` |
| `maintenance/backup/media/` | `backup_media` |
| `maintenance/cleanup/tickets/` | `cleanup_tickets` |
| `maintenance/cleanup/tickets/preview/` | `cleanup_tickets_preview` |
| `maintenance/cleanup/notifications/` | `cleanup_notifications` |
| `maintenance/cleanup/notifications/preview/` | `cleanup_notifications_preview` |

## Tickets — `/tickets/`

| Path | Name |
|---|---|
| `` | `tickets_list` |
| `dashboard/` | `dashboard` |
| `dashboard/export/` | `dashboard_export` |
| `settings/` | `settings` |
| `create/` | `ticket_create` |
| `<int:ticket_id>/edit/` | `ticket_update` |
| `<int:ticket_id>/` | `ticket_detail` |
| `<int:ticket_id>/drawer/` | `ticket_drawer` |
| `category-options/` | `ticket_category_options` |
| `<int:ticket_id>/message/` | `post_message` |
| `message/<int:message_id>/delete/` | `delete_message` |
| `message/<int:message_id>/edit/` | `edit_message` |
| `<int:ticket_id>/status/` | `update_status` |
| `<int:ticket_id>/pick/` | `pick_ticket` |
| `<int:ticket_id>/merge/` | `merge_ticket` |
| `search-options/` | `ticket_search_options` |
| `merge-preview/<int:ticket_id>/` | `ticket_merge_preview` |
| `<int:ticket_id>/transfer/` | `transfer_ticket` |
| `<int:ticket_id>/transfer/accept/` | `accept_transfer` |
| `<int:ticket_id>/transfer/deny/` | `deny_transfer` |
| `<int:ticket_id>/transfer/cancel/` | `cancel_transfer` |

## Notifications — `/notifications/`

| Path | Name |
|---|---|
| `api/` | `notifications_list` |
| `mark-read/` | `notifications_mark_read` |
| `mark-read/<int:notification_id>/` | `notification_mark_read` |
| `delete/<int:notification_id>/` | `notification_delete` |
| `clear-read/` | `notifications_clear_read` |

## News — `/news/`

| Path | Name |
|---|---|
| `` | `news_list` |
| `create/` | `news_create` |
| `<int:pk>/edit/` | `news_update` |
| `<int:pk>/delete/` | `news_delete` |

## Knowledge base — `/kb/`

| Path | Name |
|---|---|
| `` | `kb_list` |
| `create/` | `kb_create` |
| `<int:pk>/` | `kb_detail` |
| `<int:pk>/edit/` | `kb_update` |
| `<int:pk>/delete/` | `kb_delete` |
| `search-suggest/` | `kb_search_suggest` |
| `ticket-search/` | `kb_ticket_search` |
| `categories/` | `kb_category_list` |
| `categories/add/` | `kb_category_create` |
| `categories/<int:pk>/edit/` | `kb_category_update` |
| `categories/<int:pk>/delete/` | `kb_category_delete` |

`kb_category_*` manages **`kb.Category`**, not `core.Category`.

## WebSocket routes (`config/asgi.py`)

Mounted under the Channels `URLRouter` (same host as HTTP; scheme `ws:` / `wss:`).

| Pattern | Consumer |
|---|---|
| `ws/tickets/` | `tickets.consumers.TicketListConsumer` |
| `ws/tickets/<ticket_id>/` | `tickets.consumers.TicketChatConsumer` |
| `ws/notifications/` | `notifications.consumers.NotificationConsumer` |

Auth failures close with code **4401**. See [realtime.md](realtime.md).

## Related docs

- [Architecture](architecture.md)
- [Realtime](realtime.md)
- [Permissions and scoping](permissions-and-scoping.md)
