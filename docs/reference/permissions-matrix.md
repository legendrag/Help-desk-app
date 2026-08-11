# Permissions matrix

Canonical lookup of every `core.Role` boolean flag: UI label, field name, and what it unlocks.

**Audience:** Administrators configuring roles, and developers checking authorization.

Related: [Users and roles](../admin-guide/users-and-roles.md) · [Settings Hub](../admin-guide/settings-hub.md)

---

## How permissions work

Access is controlled by three independent layers:

| Layer | What it is | How it relates to Role flags |
|---|---|---|
| **Role flags** | Boolean fields on `core.Role` | The tables below. Assigned to a user via `user.role`. |
| **`user_type`** | `branch` (Needs Support) or `support` (Support Agent) | Orthogonal to Role flags. Scopes which tickets a user sees (branch vs department) and which UI flows apply (e.g. Pick is for support). |
| **Superuser** | Django `is_superuser` | Bypasses Role flag checks. Superusers can perform actions regardless of Role flags. |

A user without a Role has no Role flags (treated as denied for gated actions). Superusers do not need Role flags.

### Admin-name trap

If a Role’s **name** is exactly `admin` (case-insensitive after strip), saving that Role **auto-enables every boolean permission field**. Naming a role “admin” is not the same as Django superuser, but it effectively grants all Role flags. Prefer a descriptive name (for example “Team Lead”) and set only the flags you need.

---

## Ticket

| UI label | Field name | What it unlocks |
|---|---|---|
| Create Ticket | `can_create_ticket` | Open the ticket creation form and create tickets. |
| Edit Ticket | `can_update_ticket` | Edit ticket fields (title, category, priority, and related editable attributes) after creation. |
| Pick Ticket | `can_pick_ticket` | **Pick** (list) / **Accept** (detail) on an unassigned ticket in the agent’s department. Assigns the ticket to the current user and typically moves it to In Progress. |
| Update Ticket Status | `can_update_status` | Change ticket status from the action bar (for example Close, Wait for User, In Progress). Also required to **merge** tickets. |
| Update Status after closed | `can_update_closed_ticket` | Update or reopen a ticket after it has been closed (beyond the default same-department support reopen path). |
| Send Message | `can_send_message` | Use the chat composer / send messages on tickets where chat is otherwise allowed. |
| Edit Message | `can_edit_message` | Edit your own chat messages after sending (support UI; not for branch users in the default templates). |
| Delete Message | `can_delete_message` | Delete your own chat messages (support UI; not for branch users in the default templates). |

---

## Dashboard and settings

| UI label | Field name | What it unlocks |
|---|---|---|
| Access Dashboard | `can_access_dashboard` | Open the analytics dashboard (ticket volumes, status breakdown, and related charts). |
| View Agent Leaderboard | `can_view_leaderboard` | See the agent leaderboard section on the dashboard. |
| Access Settings | `can_access_settings` | Open the [Settings Hub](../admin-guide/settings-hub.md) and view settings list tabs. Create/edit/delete still need the matching entity flags below. |

---

## Users

Requires **Access Settings** to reach the Users tab. CRUD buttons are gated separately.

| UI label | Field name | What it unlocks |
|---|---|---|
| Create User | `can_create_user` | Add new user accounts in Settings. |
| Edit User | `can_update_user` | Edit existing users (profile, role, branch/department, status, and related fields). |
| Delete User | `can_delete_user` | Delete user accounts from Settings. |

---

## Branches

| UI label | Field name | What it unlocks |
|---|---|---|
| Create Branch | `can_create_branch` | Add branch locations in Settings. |
| Edit Branch | `can_update_branch` | Edit branch name and code. |
| Delete Branch | `can_delete_branch` | Delete a branch (subject to referential protection when still in use). |

---

## Departments

| UI label | Field name | What it unlocks |
|---|---|---|
| Create Department | `can_create_department` | Add support departments in Settings. |
| Edit Department | `can_update_department` | Edit department names. |
| Delete Department | `can_delete_department` | Delete a department (subject to referential protection when still in use). |

---

## Categories

Ticket categories under a department (not Knowledge Base categories).

| UI label | Field name | What it unlocks |
|---|---|---|
| Create Category | `can_create_category` | Add ticket categories (with default priority) under a department. |
| Edit Category | `can_update_category` | Edit ticket categories. |
| Delete Category | `can_delete_category` | Delete ticket categories. |

---

## Roles

| UI label | Field name | What it unlocks |
|---|---|---|
| Create Role | `can_create_role` | Create new Role permission sets in Settings. |
| Edit Role | `can_update_role` | Edit Role names, descriptions, and permission flags. |
| Delete Role | `can_delete_role` | Delete Role records. |

---

## Email

| UI label | Field name | What it unlocks |
|---|---|---|
| Manage Email Settings | `can_manage_email` | Configure SMTP (`EmailSetting`), notification event toggles, email templates, and send-test from Settings. |

---

## News

| UI label | Field name | What it unlocks |
|---|---|---|
| Manage News | `can_manage_news` | Create and manage announcements / news items. |

---

## Knowledge Base

| UI label | Field name | What it unlocks |
|---|---|---|
| Access Knowledge Base | `can_access_kb` | Open the Knowledge Base UI. Also used for limited ticket view bypass when a ticket has a published related KB article. |
| Manage Knowledge Base | `can_manage_kb` | Create, edit, and publish KB articles and manage KB categories (including the Settings Hub KB Categories tab). |

---

## Maintenance

| UI label | Field name | What it unlocks |
|---|---|---|
| Manage System Maintenance | `can_manage_maintenance` | Use the Settings Hub Maintenance tab (ticket/message export, media zip download, and related cleanup tools). |

---

## Quick checklist

When designing a role, ask:

1. What is the user’s `user_type` (branch vs support)? That scopes tickets independently of flags.
2. Does the user need Settings at all? If yes, grant `can_access_settings`, then only the CRUD flags they need.
3. Avoid naming the role `admin` unless you intend every flag to turn on.
4. Prefer superuser only for true system operators; use Role flags for day-to-day admins.

See [Users and roles](../admin-guide/users-and-roles.md) for assignment workflows and recommended role patterns.
