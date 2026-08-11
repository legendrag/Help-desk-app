# Settings Hub

Open the in-app administrative settings console at `/tickets/settings/` and manage organization, users, roles, email, and maintenance from one place.

**Audience:** In-app administrators with **Access Settings** (`can_access_settings`), or a Django superuser.

## Overview

The Settings Hub is a tabbed panel loaded inside the main app (Django Templates + HTMX). Each tab swaps the content area without a full page reload. Use it to configure the entities that tickets, users, and notifications depend on.

Open it from the sidebar (**Settings**), or go directly to `/tickets/settings/`.

You need **Access Settings** on your role to open the hub and view list tabs. Superusers always have access. Creating, editing, or deleting records requires the matching granular permission for that entity (see [Users and roles](users-and-roles.md) and the [permissions matrix](../reference/permissions-matrix.md)).

## Tabs

| Tab | Always visible? | Required to see / use |
|---|---|---|
| Branches | Yes | View: `can_access_settings`. CRUD: branch create/edit/delete flags |
| Departments | Yes | View: `can_access_settings`. CRUD: department flags |
| Categories | Yes | View: `can_access_settings`. CRUD: category flags |
| Roles | Yes | View: `can_access_settings`. CRUD: role flags |
| Users | Yes | View: `can_access_settings`. CRUD: user flags |
| Email Settings | Yes | View: `can_access_settings`. Manage SMTP/templates: **Manage Email Settings** |
| KB Categories | Conditional | Superuser or **Manage Knowledge Base** (`can_manage_kb`) |
| Maintenance | Conditional | Superuser or **Manage System Maintenance** (`can_manage_maintenance`) |

The default tab on load is **Branches**.

## Viewing vs changing data

- **Viewing lists** requires **Access Settings**. Without it, the Settings entry is unavailable (except for superusers).
- **Add / Edit / Delete** buttons and forms are gated per entity:
  - Branches → Create / Edit / Delete Branch
  - Departments → Create / Edit / Delete Department
  - Categories → Create / Edit / Delete Category
  - Roles → Create / Edit / Delete Role
  - Users → Create / Edit / Delete User
  - Email Settings → Manage Email Settings (covers SMTP rows, templates, and send-test)
- Conditional tabs (KB Categories, Maintenance) hide entirely unless you have the matching manage flag (or are a superuser).

A user can have **Access Settings** to browse lists without any create/edit/delete flags. That is useful for read-only auditors.

## What each tab is for

| Tab | Purpose | Detailed doc |
|---|---|---|
| Branches | Locations that own tickets and scope branch users | [Organization](organization.md) |
| Departments | Support queues that own categories and scope agents | [Organization](organization.md) |
| Categories | Issue types under a department, with default priority | [Organization](organization.md) |
| Roles | Named permission sets assigned to users | [Users and roles](users-and-roles.md) |
| Users | Accounts, user type, branch/department, role | [Users and roles](users-and-roles.md) |
| Email Settings | SMTP (database), notification toggles, templates | [Email settings](email-settings.md) |
| KB Categories | Knowledge Base category management | [Knowledge base](../user-guide/knowledge-base.md) |
| Maintenance | Exports, media zip, cleanup tools | [Maintenance](maintenance.md) |

## Day-to-day workflow

1. Confirm your account has **Access Settings** (and any CRUD flags you need).
2. Open **Settings** from the sidebar.
3. Select a tab. The content panel loads the list for that entity.
4. Use **Add** (when allowed) to create a record, or open an existing row to edit or delete.
5. For email, configure one active SMTP row, enable event toggles, customize templates, then send a test — see [Email settings](email-settings.md).
6. For destructive cleanup or downloads, use the **Maintenance** tab — see [Maintenance](maintenance.md).

## Related docs

- [Organization](organization.md) — branches, departments, categories, and delete protection
- [Users and roles](users-and-roles.md) — user types, full permission table, admin-name trap
- [Email settings](email-settings.md) — SMTP, templates, merge tokens
- [Maintenance](maintenance.md) — exports and cleanup
- [Permissions matrix](../reference/permissions-matrix.md) — quick lookup of flags
- [Getting started](../user-guide/getting-started.md) — how branch vs support users experience the app
