# Glossary

Short definitions of product and technical terms used across mlamehticket documentation.

**Audience:** Everyone reading the docs or configuring the app.

Related: [Permissions matrix](permissions-matrix.md) · [Getting started](../user-guide/getting-started.md) · [Configuration](../operations/configuration.md)

---

## Branch

An organizational location (name + unique **code**) that owns tickets and scopes **Needs Support** users. Branch users typically see tickets for their assigned branch. The branch code is used in the [ticket number format](#ticket-number-format).

## Department

A support queue (for example IT Support or Facilities). Support agents are scoped to a department. Ticket categories belong to a department. Transfer targets are same-department agents.

## Category (ticket vs KB)

Two different “category” concepts exist:

| Kind | Model | Purpose |
|---|---|---|
| **Ticket category** | `core.Category` | Issue type under a **Department**, with a default priority. Chosen when creating a ticket. Managed in Settings under Categories. |
| **KB category** | `kb.Category` | Folder/grouping for Knowledge Base articles (name, description, icon). Managed from the KB UI / Settings KB Categories tab when allowed. |

Do not confuse Settings “Categories” (ticket) with Knowledge Base categories.

## Role

A named set of boolean permission flags (`core.Role`) assigned to a user. Role flags gate actions such as creating tickets, picking, merging, and opening Settings. See [Permissions matrix](permissions-matrix.md). Orthogonal to `user_type` (branch vs support).

## Needs Support (branch user)

`user_type = branch`. A user who opens tickets for their branch and chats on branch tickets. UI label: **Needs Support**. Does not Pick, Transfer, or Merge tickets in the normal agent workflow.

## Support Agent

`user_type = support`. A user who works department tickets: Pick/Accept, chat when assigned, change status, transfer, and merge (subject to Role flags). UI label: **Support Agent**.

## Pick / Accept

Two UI entry points for the same ownership action on an **unassigned** ticket:

- **Pick** — from the ticket list.
- **Accept** — from the ticket detail action area.

Requires **Pick Ticket** (`can_pick_ticket`) unless the user is a superuser. Assigns the ticket to the current agent and typically sets status to In Progress.

## Waiting / Wait for User

Ticket status `waiting_for_branch`. UI action/label is often **Wait for User**; the status display may show **Waiting**. Means the agent is waiting on a reply or action from the branch. Time spent in this status accumulates for pending-duration metrics.

## Merged

Ticket status `merged`. The ticket was folded into another (primary) ticket via **Merge Ticket**. The secondary ticket keeps a `merged_into` link to the primary; chat and actions on the merged ticket are limited. Merging requires **Update Ticket Status** (`can_update_status`). See [Transfer and merge](../user-guide/transfer-and-merge.md).

## Transfer

Hand assignment of a ticket to another **same-department** support agent. The assignee (or a superuser) requests a transfer; the target **Accept**s or **Deny**s; the requester can **Cancel Request** while pending. See [Transfer and merge](../user-guide/transfer-and-merge.md).

## Ticket number format

Auto-generated unique id when a ticket is created:

```text
{BRANCH_CODE}-{YYYYMMDD}-{NNNN}
```

Example: `MAIN-20260730-0001`

- `BRANCH_CODE` — uppercase branch code (fallback `BR` if missing).
- `YYYYMMDD` — creation date.
- `NNNN` — four-digit daily sequence for that branch prefix.

## Settings Hub

In-app admin console (sidebar **Settings Hub** / Settings) for branches, departments, categories, roles, users, email, KB categories, and maintenance. Requires **Access Settings** (`can_access_settings`) or superuser. See [Settings Hub](../admin-guide/settings-hub.md).

## Daphne

ASGI server used to run the app in production so HTTP and WebSockets (live chat / notifications) work on one process. Prefer Daphne over `runserver` for real-time features. See [Deployment](../operations/deployment.md).

## HTMX

Library used for partial page updates without a full SPA framework. Views detect `HX-Request` and return HTML fragments (modals, list refresh, merge search, settings tabs). Server responses may send `HX-Trigger` headers for client events.

## In-app notification

A notification row shown in the top-bar **bell** dropdown (`InAppNotification`). Covers ticket events, transfers, announcements, and similar types. Separate from email and web push. Cleaned by `cleanup_notifications` — see [Management commands](management-commands.md).

## Web push

Optional browser/OS push via `django-webpush`. Users enable it from the notification dropdown. Delivers alerts when the app is in the background (browser and device permitting). Independent of the in-app bell and of email.

## EmailSetting

Database-stored SMTP configuration and per-event email toggles (new ticket, picked, message, status, update, announcement). Only one row may be active at a time. Templates use merge tokens. Managed under Settings when the role has **Manage Email Settings**. Requires a correct `SITE_URL` for absolute links in messages.

## SITE_URL

Environment / settings value for the public base URL of the app **without a trailing slash** (for example `https://helpdesk.example.com` or `http://192.168.1.10:8000`). Used to build absolute links in notification emails. Wrong or empty values produce broken or relative links. See [Configuration](../operations/configuration.md).

## Locale cookie

Language preference is stored in the `django_language` cookie (English / Arabic). `LocaleMiddleware` applies it. There is no `/ar/` URL prefix; the same paths serve both languages. Users switch language under sidebar Preferences.

## Forced password change

When `requires_password_change` is true on a user (for example a newly bootstrap-created admin), middleware forces a password change before normal use. Bootstrap admins created via `DEFAULT_SUPERADMIN_PASSWORD` on migrate are set this way.

## InMemoryChannelLayer

Default Django Channels backend for WebSocket groups. Events stay **in-process**. Multiple Daphne workers do not share realtime state with this backend; use a single process or introduce a shared channel layer for multi-worker setups. See [Security hardening](../operations/security-hardening.md) and [Troubleshooting](../operations/troubleshooting.md).
