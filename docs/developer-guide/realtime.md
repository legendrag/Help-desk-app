# Realtime

Django Channels consumers, channel groups, event shapes, and close codes used by mlamehticket.

**Audience:** Developers changing live ticket list/chat/notification behavior or debugging WebSocket auth.

## Runtime assumptions

- ASGI app: `config.asgi.application` (Daphne).
- HTTP and WebSocket share `AuthMiddlewareStack` session authentication.
- Channel layer: **`InMemoryChannelLayer`** — broadcasts stay inside one process. Multiple Daphne workers will not see each other’s groups.
- There is **no Redis** channel layer in the default settings.

Routing is assembled in `config/asgi.py` from `tickets.routing` and `notifications.routing`.

## Consumers and paths

| Path | Consumer | Purpose |
|---|---|---|
| `ws/tickets/` | `TicketListConsumer` | Live ticket list / row refresh events |
| `ws/tickets/<ticket_id>/` | `TicketChatConsumer` | Per-ticket chat, typing, message events |
| `ws/notifications/` | `NotificationConsumer` | Per-user in-app notification push |

## Groups

| Group name | Who joins | Who sends |
|---|---|---|
| `ticket_{id}` | Chat clients for that ticket | `tickets.realtime.broadcast_ticket_message` and related `group_send` |
| `ticket_list` | Superusers on the list socket | List broadcasts always include this group |
| `ticket_list_branch_{id}` | Branch users with that `branch_id` | Broadcasts that pass `branch_id` |
| `ticket_list_department_{id}` | Support users with that `department_id` | Broadcasts that pass `department_id` |
| `user_{id}_notifications` | That user’s notification socket | `notifications.services._broadcast_notification` |

`broadcast_ticket_list_event(event_type, payload, branch_id=…, department_id=…)` always targets `ticket_list` and optionally the branch/department groups.

## Close codes

| Code | Meaning |
|---|---|
| **4401** | Not authenticated — anonymous connect rejected |
| **4403** | Authenticated but not allowed (wrong org scope, missing branch/department, or ticket access denied) |

Clients should treat **4401** as a hard auth failure (stop auto-reconnect / re-login). Other disconnects may reconnect.

## Ticket chat (`TicketChatConsumer`)

### Connect

1. Require authenticated user → else **4401**.
2. Require `user_in_ticket_org(user, ticket)` (strict org match; **no KB bypass**) → else **4403**.
3. Join `ticket_{ticket_id}` and accept.

HTTP detail views may allow KB-related read access across org boundaries; the chat WebSocket does **not**. Cross-org users can view via HTTP when KB bypass applies, but cannot subscribe to live chat.

### Client → server

| Incoming JSON | Behavior |
|---|---|
| `{ "type": "typing" }` | Broadcasts `event: "typing"` with sender id/username to the ticket group |
| `{ "message": "…", "reply_to": optionalId }` | Creates a `TicketMessage` if the user may send; empty message returns an error |

Send rules (server-side):

- Role must have `can_send_message` (superusers always allowed).
- Must still pass `user_in_ticket_org`.
- Support agents (non-superuser) may only send when `ticket.assigned_to_id == user.id`.
- Closed / merged tickets reject new messages.

Successful creates are typically also fanned out from model signals via `broadcast_ticket_message` (`event: "message_created"`).

### Server → client

Handler `chat_event` sends:

```json
{
  "event": "<name>",
  "payload": { }
}
```

Common event names (from app broadcasts / UI expectations):

| Event | Typical trigger |
|---|---|
| `message_created` | New chat or system message |
| `message_edited` | Message text updated |
| `message_deleted` | Message removed |
| `ticket_status_changed` | Status update |
| `ticket_picked` | Pick action |
| `typing` | Peer typing indicator |

## Ticket list (`TicketListConsumer`)

### Connect

1. Require auth → else **4401**.
2. Choose group:
   - Superuser → `ticket_list`
   - `user_type == branch` with `branch_id` → `ticket_list_branch_{branch_id}`
   - `user_type == support` with `department_id` → `ticket_list_department_{department_id}`
   - Otherwise → **4403**

### Server → client

Handler `ticket_event` sends `{ "event", "payload" }`. Event types are string labels from callers (for example create/update/delete style list events from `tickets.signals` and view helpers).

The browser typically responds by HTMX-refreshing the list partial rather than patching individual DOM nodes in JS.

## Notifications (`NotificationConsumer`)

### Connect

Authenticated user only (else **4401**). Joins `user_{id}_notifications`.

### Server → client

Handler `notification_event` sends the payload object directly (not wrapped as `{event, payload}`):

```json
{
  "id": 1,
  "title": "…",
  "message": "…",
  "title_ar": "…",
  "message_ar": "…",
  "link": "/tickets/123/",
  "notification_type": "new_ticket",
  "is_read": false,
  "created_at": "…"
}
```

## Broadcast helpers

| Helper | Module | Effect |
|---|---|---|
| `broadcast_ticket_message(ticket_id, payload)` | `tickets.realtime` | `type: chat.event`, `event: message_created` |
| `broadcast_ticket_list_event(event_type, payload, …)` | `tickets.realtime` | `type: ticket.event` to list groups |
| `_broadcast_notification(notification)` | `notifications.services` | `type: notification.event` to `user_{id}_notifications` |

Signals in `tickets.signals` bridge model saves to list/chat broadcasts and notification service entrypoints.

## Related docs

- [Architecture](architecture.md)
- [URL reference](url-reference.md)
- [Notifications internals](notifications-internals.md)
- [Permissions and scoping](permissions-and-scoping.md)
