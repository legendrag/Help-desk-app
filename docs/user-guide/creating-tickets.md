# Creating tickets

Open a new support ticket for your branch or department workflow.

**Audience:** Users with permission to create tickets (typically Needs Support / branch staff; also roles with create-ticket permission).

## Who can create tickets

You need a role that allows creating tickets (or a superuser account). On the ticket list, **+ New Ticket** appears when you are allowed to create.

Branch users (`Needs Support`) create tickets for their own branch only. Support agents create tickets only when their role includes create-ticket permission.

## Before you start

Have ready:

- A clear title and description of the issue
- Department and category (if prompted by the form)
- Priority level
- Optional client name or other form fields your organization uses
- Optional attachments (see limits below)

## Create a ticket (step by step)

1. Open the ticket list (main tickets page after login).
2. Click **+ New Ticket**.
3. Fill in the create form:
   - **Title** and description of the problem or request.
   - **Branch** — for Needs Support users, Branch is locked to your assigned branch and cannot be changed.
   - **Department**, **category**, and **priority** as required by your organization.
   - Any other fields shown on the form (for example client name).
4. Attach files if needed (optional).
5. Submit the form.

After success you receive a ticket number in the format `{BRANCH_CODE}-{YYYYMMDD}-{NNNN}` (for example `BR-20260730-0001`). The new ticket starts in **Open** status unless your process immediately routes it otherwise.

You can also open the dedicated create page (**Create New Ticket**) when the app navigates there from the button.

## Branch locked on create

For **Needs Support** accounts:

- The Branch field is disabled and pre-filled with your branch.
- You cannot open a ticket for another branch.
- The generated ticket number uses your branch code.

This keeps every ticket scoped to the correct location.

## Attachments on create

Attachments follow the same rules as chat and Knowledge Base uploads:

| Rule | Value |
|---|---|
| Maximum size | 10 MB per file |
| Allowed types | `.pdf`, `.docx`, `.xlsx`, `.jpg`, `.jpeg`, `.png` |

Files outside these types or over the size limit are rejected. Prefer clear screenshots or documents that help the agent diagnose the issue.

## After you create

- The ticket appears in your branch list (Needs Support) or in the department list for agents who can see it.
- Support agents in the department can **Pick** / **Accept** it.
- You can open the ticket to chat (branch users can chat on any ticket in their branch). See [Working with tickets](working-with-tickets.md).
- Watch the [notification bell](notifications.md) for picks, replies, and status changes.
- Announcement cards above the list are unrelated to your new ticket but may carry operational notices — see [Announcements](announcements.md).

## Tips for better tickets

- Use a specific title (what failed, where, and for whom).
- Include steps already tried.
- Attach screenshots or export files when they show the error.
- Do not put passwords or secrets in the description or attachments.

## Related pages

- [Getting started](getting-started.md) — roles, statuses, ticket numbers
- [Working with tickets](working-with-tickets.md) — chat, status, action bar
- [Notifications](notifications.md)
- [Knowledge Base](knowledge-base.md) — check for known solutions before opening a duplicate issue
