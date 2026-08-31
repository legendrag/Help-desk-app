# Working with tickets

Find tickets, chat, change status, and use the agent action bar.

**Audience:** Needs Support (branch) users and Support Agents working tickets day to day.

## Ticket list

The tickets page lists work you are allowed to see:

- **Needs Support** — only tickets for your branch.
- **Support Agent** — tickets for your department.

Use filters and search on the page (status, assignment, branch where available, and text search) to narrow the list. Open a ticket by clicking its ticket number or row link.

### List actions

| Control | Who | What it does |
|---|---|---|
| **+ New Ticket** | Roles with create permission | Opens create flow — [Creating tickets](creating-tickets.md) |
| **Pick** | Support agents (with pick permission) on unassigned tickets | Assigns the ticket to you from the list |
| **Details** | Users who can see the ticket | Opens the Details drawer / preview from the list |

Announcement cards may appear above the list — [Announcements](announcements.md).

## Ticket detail

The detail page shows the ticket header, chat thread, composer (when allowed), and actions.

### Details drawer

Use **Details** to open the details drawer. It shows ticket metadata and related information (for example related Knowledge Base articles when present). Use the copy icon next to the ticket number to copy that number. Close the drawer when you are done.

## Ticket numbers and statuses

Ticket numbers look like `BR-20260730-0001`. Statuses you will see:

- **Open**
- **In Progress**
- **Wait for User** (system value `waiting_for_branch`)
- **Closed**
- **Merged**

Merged tickets show a merged state and banner; chat and actions are limited. See [Transfer and merge](transfer-and-merge.md).

## Chat

### Who can chat

| Role | Chat rule |
|---|---|
| Needs Support (branch) | Can chat on any ticket in their branch |
| Support Agent | Can chat only when assigned to that ticket |
| Superuser | Can chat as allowed by the app for admins |

If you are a support agent viewing an unassigned or someone else’s ticket, you typically will not see a working composer until you **Accept** / **Pick** the ticket (unless you are a superuser).

### Sending messages

1. Open the ticket.
2. Type in the chat composer.
3. Send the message. Real-time delivery updates the thread for other participants.

### Attachments in chat

- Maximum **10 MB** per file.
- Allowed extensions: `.pdf`, `.docx`, `.xlsx`, `.jpg`, `.jpeg`, `.png`.
- Drag and drop files onto the chat area, or use the attachment control on the composer.
- Image attachments can be previewed; other types download via link.

The same attachment rules apply to Knowledge Base articles ([Knowledge Base](knowledge-base.md)).

### Message Details

Use **Details** on a message menu when you need message-level detail (for example timing or metadata shown in the UI).

## Pick and Accept (support agents)

Unassigned department tickets can be claimed:

1. From the **list**, click **Pick** on the ticket row (when shown).
2. Or open the ticket and click **Accept** on the detail action area.

After you are assigned:

- You can chat on that ticket.
- The full action bar becomes available (Close, Wait for User, In Progress, Merge Ticket, Transfer Ticket, and related menu items).

You need pick permission on your role (`Pick Ticket`) unless you are a superuser.

## Action bar (assigned agent or superuser)

When you are the assignee (or a superuser), the left action bar on the ticket detail page provides:

| Control | Purpose |
|---|---|
| **Accept** | Shown when the ticket is still unassigned (with pick permission) |
| **Close** | Closes the ticket (confirmation modal) |
| **Wait for User** | Sets status to waiting for the branch (`waiting_for_branch`) |
| **In Progress** | Marks the ticket as actively worked |
| **Merge Ticket** | Merge another ticket into this one — [Transfer and merge](transfer-and-merge.md) |
| **Transfer Ticket** | Request transfer to another same-department agent — [Transfer and merge](transfer-and-merge.md) |

Use the action bar toggle/menu to choose an action, then execute. Some actions ask for confirmation (close, merge, transfer).

Status updates generally require permission to update status (`can_update_status` on the role) and assignment rules: non-superusers update status on tickets assigned to them.

### Reopen

When a ticket is **Closed**, eligible support users (same organization rules) see **Reopen**. Reopening returns the ticket to active work so chat and actions can continue under your process.

### Merged tickets

If status is **Merged**, the action bar shows that the ticket is merged instead of the normal controls. Follow the banner to the primary ticket when provided.

## Branch user workflow

Typical Needs Support flow:

1. [Create a ticket](creating-tickets.md) (branch locked).
2. Watch for an agent to pick it up ([Notifications](notifications.md)).
3. Reply in chat when the agent asks questions or when status is **Wait for User**.
4. Confirm resolution; the agent closes the ticket.

Branch users do not use Pick/Accept, Transfer, or Merge.

## Support agent workflow

Typical Support Agent flow:

1. Open the department ticket list.
2. **Pick** or **Accept** an unassigned ticket.
3. Chat with the branch; set **In Progress** or **Wait for User** as needed.
4. Transfer or merge if the work belongs with another ticket or agent ([Transfer and merge](transfer-and-merge.md)).
5. **Close** when done; **Reopen** only if work must resume.

## Related pages

- [Getting started](getting-started.md)
- [Creating tickets](creating-tickets.md)
- [Transfer and merge](transfer-and-merge.md)
- [Notifications](notifications.md)
- [Knowledge Base](knowledge-base.md)
- [Dashboard](dashboard.md)
