# Maintenance

Export ticket text, download media archives, and clean up old closed tickets or in-app notifications from the Settings Hub.

**Audience:** Administrators with **Manage System Maintenance** (`can_manage_maintenance`), or a Django superuser.

## Access

1. Your role must include **Manage System Maintenance** (or you must be a superuser).
2. Open [Settings Hub](settings-hub.md) (`/tickets/settings/`).
3. Select the **Maintenance** tab (shown only when the permission above is present).

Viewing other Settings tabs still requires **Access Settings**. Maintenance actions themselves are gated by `can_manage_maintenance`.

## Export and backup

The **Export & Backup** panel offers two downloads.

### Export Tickets & Messages

| Detail | Behavior |
|---|---|
| Output | Plain-text `.txt` file (`tickets_export_YYYYMMDD_HHMM.txt`) |
| Contents | All tickets with metadata, description, and chat messages (including system messages and attachment filenames) |
| Restorable? | **No** — human-readable archive only; not a database restore format |

Use this for audits, offline review, or evidence packs. For a real database backup, use operations tooling — see [Backup and restore](../operations/backup-restore.md).

### Download Media Zip

| Detail | Behavior |
|---|---|
| Output | `media_backup.zip` |
| Contents | Files under the server `MEDIA_ROOT` (uploaded attachments and similar) |
| Restorable? | Zip of media files only — not a full app restore |

Pair a media zip with a proper database backup if you need disaster recovery.

### Rate limit

Both downloads enforce a **5-minute per-user** cooldown (separate counters for ticket export and media zip). If you retry too soon, the UI shows a rate-limit message (HTTP 429) with the remaining wait in seconds.

## System cleanup

Cleanup tools permanently delete data. Each flow shows a **preview** count first; deletion runs only after you confirm.

### Cleanup Old Tickets

Deletes **closed** tickets whose `updated_at` is older than the selected age, including related messages. Attachment files on disk are removed when possible before the database rows are deleted.

| Option | Meaning |
|---|---|
| Older than 30 days | Closed tickets idle longer than 30 days |
| Older than 60 days | Same for 60 days |
| Older than 90 days | Same for 90 days |
| Older than 1 year | Same for 365 days |

Workflow:

1. Choose a period.
2. Click **Preview** — see how many tickets would be removed (or a “nothing to clear” notice).
3. Click **Confirm Delete** only if the count is expected.
4. Cancel / close to abort without deleting.

Open, in-progress, waiting, and merged tickets are **not** removed by this tool — only `closed` tickets past the cutoff.

Because ticket FKs to organization records use `PROTECT`, cleaning old closed tickets can unblock later deletion of unused branches, departments, or categories — see [Organization](organization.md).

### Cleanup Notifications

Deletes in-app notifications (`InAppNotification`) by age:

| Control | Default | Meaning |
|---|---|---|
| Read older than | 30 days | Delete **read** notifications older than this many days |
| All older than | 90 days | Delete **all** notifications (read or unread) older than this absolute age |

Options in the UI:

- Read: 14 / 30 / 60 days
- All: 60 / 90 / 180 days

Workflow matches tickets: **Preview** → review counts → **Confirm Delete** or cancel.

This does not delete tickets or chat history — only notification bell records. See [Notifications](../user-guide/notifications.md) for the end-user side.

## Safety notes

- Exports and zips are **not** substitutes for scheduled database backups.
- Ticket `.txt` export is **not restorable** into mlamehticket.
- Cleanup is irreversible. Prefer longer retention until you have confirmed backups.
- Downloads are logged server-side (username, id, client address).
- Rate limits reduce accidental repeated heavy downloads; they are not a substitute for access control.

## Related docs

- [Settings Hub](settings-hub.md)
- [Users and roles](users-and-roles.md) — `can_manage_maintenance`
- [Organization](organization.md) — PROTECT and why cleanup may be needed before deletes
- [Backup and restore](../operations/backup-restore.md)
- [Permissions matrix](../reference/permissions-matrix.md)
