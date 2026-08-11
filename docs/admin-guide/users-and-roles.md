# Users and roles

Create accounts, assign user types, and control access with granular role permissions.

**Audience:** Administrators managing people and permissions in the [Settings Hub](settings-hub.md) (**Access Settings**, plus user/role CRUD flags).

## Concepts

| Concept | Meaning |
|---|---|
| User | Login account with type, optional branch/department, and a role |
| Role | Named set of boolean permissions (`core.Role`) |
| User type | `branch` (**Needs Support**) or `support` (**Support Agent**) — scopes what tickets the user sees |
| Superuser | Django `is_superuser`; bypasses most permission checks |

Permissions live on the **role**, not on the user row. Change a role once to update every user assigned to it.

For a compact cheat sheet, see the [permissions matrix](../reference/permissions-matrix.md).

## User types

| System value | UI label | Ticket scope |
|---|---|---|
| `branch` | Needs Support | Tickets for the user's assigned **branch** |
| `support` | Support Agent | Tickets for the user's assigned **department** |

### Needs Support (`branch`)

- Sees only tickets belonging to their branch.
- When creating a ticket, **Branch** is locked to their branch.
- Can chat on tickets in their branch (including tickets already assigned to an agent), subject to message permissions.

### Support Agent (`support`)

- Sees tickets for their department.
- Uses **Pick** / **Accept** to take ownership of unassigned tickets (requires **Pick Ticket**).
- Chat and action-bar controls depend on assignment and role flags.

Day-to-day behavior for each type is covered in [Getting started](../user-guide/getting-started.md) and [Working with tickets](../user-guide/working-with-tickets.md).

### Superuser

A Django superuser bypasses most role checks (Settings Hub, maintenance, email manage, ticket actions, and similar gates). Prefer a carefully permissioned role for routine admin work; reserve superuser for break-glass access.

## Managing users

Open [Settings Hub](settings-hub.md) → **Users**.

Typical fields include username, email, phone, password, status (active/inactive), user type, branch, department, and role. Validation ties type to org assignment: branch users need a branch; support agents need a department (and usually a role with agent capabilities).

| Action | Permission (UI label) |
|---|---|
| View list | Access Settings |
| Create | Create User |
| Edit | Edit User |
| Delete | Delete User |

## Managing roles

Open [Settings Hub](settings-hub.md) → **Roles**.

Each role has a unique **name**, optional **description**, and the boolean flags listed below.

| Action | Permission (UI label) |
|---|---|
| View list | Access Settings |
| Create | Create Role |
| Edit | Edit Role |
| Delete | Delete Role |

The built-in role named **admin** (any casing) is special — see [Admin name trap](#admin-name-trap) below. The Settings UI also excludes that role from normal edit/delete querysets so it is not casually modified like other roles.

## Full permission table

UI labels match `verbose_name` on `core.Role`. Field names are the boolean attributes used in code and in the [permissions matrix](../reference/permissions-matrix.md).

### Tickets and chat

| Field | UI label | Notes |
|---|---|---|
| `can_create_ticket` | Create Ticket | Open the ticket creation form |
| `can_update_ticket` | Edit Ticket | Edit ticket fields |
| `can_pick_ticket` | Pick Ticket | Claim / accept an unassigned ticket |
| `can_update_status` | Update Ticket Status | Change status from the action bar; **also gates merge on the backend** |
| `can_update_closed_ticket` | Update Status after closed | Change status after a ticket is closed (for example reopen flows) |
| `can_send_message` | Send Message | Post chat messages |
| `can_edit_message` | Edit Message | Edit existing messages |
| `can_delete_message` | Delete Message | Delete messages |

### Dashboard and settings access

| Field | UI label | Notes |
|---|---|---|
| `can_access_dashboard` | Access Dashboard | Open the analytics dashboard — see [Dashboard](../user-guide/dashboard.md) |
| `can_view_leaderboard` | View Agent Leaderboard | Show agent leaderboard widgets where enabled |
| `can_access_settings` | Access Settings | Open Settings Hub and view management lists |

### Users (Settings Hub)

| Field | UI label |
|---|---|
| `can_create_user` | Create User |
| `can_update_user` | Edit User |
| `can_delete_user` | Delete User |

### Branches (Settings Hub)

| Field | UI label |
|---|---|
| `can_create_branch` | Create Branch |
| `can_update_branch` | Edit Branch |
| `can_delete_branch` | Delete Branch |

### Departments (Settings Hub)

| Field | UI label |
|---|---|
| `can_create_department` | Create Department |
| `can_update_department` | Edit Department |
| `can_delete_department` | Delete Department |

### Categories (Settings Hub)

| Field | UI label |
|---|---|
| `can_create_category` | Create Category |
| `can_update_category` | Edit Category |
| `can_delete_category` | Delete Category |

### Roles (Settings Hub)

| Field | UI label |
|---|---|
| `can_create_role` | Create Role |
| `can_update_role` | Edit Role |
| `can_delete_role` | Delete Role |

### Email, news, knowledge base, maintenance

| Field | UI label | Notes |
|---|---|---|
| `can_manage_email` | Manage Email Settings | SMTP rows, templates, send test — see [Email settings](email-settings.md) |
| `can_manage_news` | Manage News | Create and manage announcements — see [Announcements](../user-guide/announcements.md) |
| `can_access_kb` | Access Knowledge Base | Read KB content — see [Knowledge base](../user-guide/knowledge-base.md) |
| `can_manage_kb` | Manage Knowledge Base | Manage KB content; also shows **KB Categories** in Settings Hub |
| `can_manage_maintenance` | Manage System Maintenance | Shows **Maintenance** tab — see [Maintenance](maintenance.md) |

## Admin name trap

When a role is **saved** with name `admin` (case-insensitive, after stripping whitespace), **every boolean permission field on that role is automatically set to `True`**.

```text
name.strip().lower() == "admin"  →  all Role BooleanFields = True
```

Implications:

- Naming any role `admin`, `Admin`, or `ADMIN` grants full application permissions on save.
- Unchecking boxes in the form does not stick if the name is still `admin` — the save hook turns them all back on.
- Do **not** use the name `admin` for a limited or custom role. Pick a different name (for example `Team Lead` or `Settings Manager`) and set only the flags you need.
- Prefer leaving the seeded full-access role alone; use explicit flags for everyone else.

## Suggested role patterns

These are examples only; adjust to your organization.

| Pattern | Typical flags |
|---|---|
| Branch staff | Create Ticket, Send Message; Access Settings usually off |
| Support agent | Pick Ticket, Update Ticket Status, Send Message; Edit Ticket as needed |
| Team lead | Agent flags plus Edit Ticket, Update Status after closed, merge-capable status flag, dashboard |
| Settings operator | Access Settings + selected create/edit/delete entity flags |
| Email admin | Access Settings + Manage Email Settings |
| Maintenance operator | Access Settings + Manage System Maintenance |

Merge in the UI/backend requires **Update Ticket Status** (`can_update_status`). Transfer flows have their own notification events; see [Transfer and merge](../user-guide/transfer-and-merge.md).

## Related docs

- [Settings Hub](settings-hub.md)
- [Organization](organization.md)
- [Permissions matrix](../reference/permissions-matrix.md)
- [Getting started](../user-guide/getting-started.md)
- [Working with tickets](../user-guide/working-with-tickets.md)
- [Transfer and merge](../user-guide/transfer-and-merge.md)
