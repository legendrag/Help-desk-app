# Organization

Define branches, departments, and categories so tickets can be scoped, routed, and prioritized correctly.

**Audience:** Administrators who manage structure in the [Settings Hub](settings-hub.md) (**Access Settings**, plus create/edit/delete flags for each entity).

## How the pieces fit together

```text
Branch  ──► tickets (location / Needs Support scope)
Department ──► categories
           ──► tickets (support queue / Support Agent scope)
Category ──► tickets (issue type + default priority)
```

- A **branch** is a physical or logical location. Branch users (`Needs Support`) see tickets for their branch.
- A **department** is a support queue. Support agents see tickets for their department.
- A **category** belongs to one department and suggests a default priority when a ticket is created.

Ticket foreign keys to branch, department, and category use Django `PROTECT`. You cannot delete an organization record that is still referenced by tickets.

Manage these entities under [Settings Hub](settings-hub.md) → **Branches**, **Departments**, and **Categories**.

## Branches

| Field | Rules |
|---|---|
| Name | Display name of the location |
| Code | Unique short code (used in ticket numbers) |

Ticket numbers include the branch code in uppercase:

```text
{BRANCH_CODE}-{YYYYMMDD}-{NNNN}
```

Example: `BR-20260730-0001`

See [Getting started](../user-guide/getting-started.md) for how ticket numbers appear to end users.

### Permissions

| Action | Permission (UI label) |
|---|---|
| View list | Access Settings |
| Create | Create Branch |
| Edit | Edit Branch |
| Delete | Delete Branch |

### Delete behavior

Deleting a branch that still has tickets fails because of `PROTECT`. Reassign or close-and-cleanup tickets first, or leave the branch in place. Branch users also reference a branch FK (usually `SET_NULL` on the user side), but ticket references are what block deletion.

## Departments

| Field | Rules |
|---|---|
| Name | Unique across the system |

Departments group categories and define which support agents see which tickets. When creating users of type **Support Agent**, assign the department they work in.

### Permissions

| Action | Permission (UI label) |
|---|---|
| View list | Access Settings |
| Create | Create Department |
| Edit | Edit Department |
| Delete | Delete Department |

### Delete behavior

- Categories under a department cascade when the department is deleted (department → category uses `CASCADE`).
- Tickets that reference the department are protected (`PROTECT`), so deletion fails if any ticket still points at that department.

Prefer renaming or leaving unused departments rather than deleting ones with ticket history.

## Categories

| Field | Rules |
|---|---|
| Department | Required foreign key |
| Name | Unique **per department** (same name may exist under different departments) |
| Default priority | `low`, `medium`, `high`, or `urgent` (default: medium) |

When a branch user creates a ticket, choosing a category can pre-fill priority from **Default priority**. Operators can still adjust priority according to ticket permissions — see [Creating tickets](../user-guide/creating-tickets.md).

### Permissions

| Action | Permission (UI label) |
|---|---|
| View list | Access Settings |
| Create | Create Category |
| Edit | Edit Category |
| Delete | Delete Category |

### Delete behavior

Deleting a category that is still used on tickets fails (`PROTECT`). Create a replacement category, stop selecting the old one on new tickets, and only delete when no tickets reference it (or after archival cleanup of closed tickets — see [Maintenance](maintenance.md)).

## Recommended setup order

1. Create **Branches** (codes should be short and stable; they appear in ticket numbers).
2. Create **Departments** for each support queue.
3. Under each department, create **Categories** with sensible default priorities.
4. Create **Roles**, then **Users**, assigning branch and/or department — see [Users and roles](users-and-roles.md).

## Related docs

- [Settings Hub](settings-hub.md)
- [Users and roles](users-and-roles.md)
- [Creating tickets](../user-guide/creating-tickets.md)
- [Working with tickets](../user-guide/working-with-tickets.md)
- [Permissions matrix](../reference/permissions-matrix.md)
