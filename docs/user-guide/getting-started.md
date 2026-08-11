# Getting started

Sign in, set preferences, and learn how branch and support roles work in mlamehticket.

**Audience:** Branch staff (Needs Support) and support agents using the help-desk day to day.

## What mlamehticket is

mlamehticket is the branch help-desk platform. Branch users open tickets for their location; support agents pick those tickets, chat, change status, transfer or merge work, and close issues. Real-time chat and the notification bell keep everyone updated without leaving the app.

## Sign in

1. Open the app URL provided by your administrator.
2. Enter your username and password.
3. Submit the login form.

### Login lockout

After **5 failed login attempts** within **5 minutes**, the account is temporarily locked. Wait about five minutes, then try again. If you still cannot sign in, contact an administrator to reset your password.

### Forced password change

If an administrator marks your account as requiring a password change, middleware redirects you to the password change screen before you can use the rest of the app. Set a new password, then continue.

You can also change your password anytime from the sidebar (**Change Password**).

## User types

Your account has one of two user types. Labels in the UI match the role name below.

| User type (system) | UI label | What you see |
|---|---|---|
| `branch` | Needs Support | Tickets for your branch only |
| `support` | Support Agent | Tickets for your department |

### Needs Support (branch)

- Sees only tickets belonging to your assigned branch.
- When creating a ticket, **Branch** is locked to your branch.
- Can chat on any ticket in your branch (including tickets assigned to a support agent).

### Support Agent (support)

- Sees tickets for your department.
- Uses **Pick** on the ticket list (or **Accept** on the ticket detail page) to take ownership of an unassigned ticket.
- Can chat only when you are the assigned agent on that ticket.
- When assigned, the full action bar is available (Close, Wait for User, In Progress, Merge Ticket, Transfer Ticket, and related controls).

Superusers can work across scopes as configured by administrators.

## Ticket statuses

Tickets move through these statuses:

| Status (system) | Typical UI label | Meaning |
|---|---|---|
| Open | Open | New or not yet actively worked |
| In Progress | In Progress | Agent is actively working the ticket |
| Waiting (`waiting_for_branch`) | Wait for User | Waiting on a reply or action from the branch |
| Closed | Closed | Work is finished |
| Merged | Merged | Ticket was merged into another ticket |

Agents set **Wait for User** and **In Progress** from the action bar. See [Working with tickets](working-with-tickets.md).

## Ticket numbers

Every ticket gets a unique number when it is created:

```text
{BRANCH_CODE}-{YYYYMMDD}-{NNNN}
```

Example: `BR-20260730-0001`

- `BRANCH_CODE` comes from the branch code (uppercase).
- `YYYYMMDD` is the creation date.
- `NNNN` is a four-digit daily sequence for that branch.

Use the ticket number when searching, merging, or referring to a ticket in chat or email.

## Sidebar and preferences

Open the sidebar (menu control in the top bar on smaller screens, or the sidebar on desktop).

### Language (EN / AR)

Under **Preferences** in the sidebar, switch between English and Arabic. The choice is stored in the `django_language` cookie. There is no `/ar/` URL prefix — the same URLs work in both languages.

### Theme (dark / light)

Also under **Preferences**, toggle **Theme** between dark and light. The preference is stored in the browser (`localStorage`).

### Other sidebar links

Depending on your role permissions, you may also see:

- **Knowledge Base** — browse or manage articles ([Knowledge Base](knowledge-base.md))
- **Dashboard** — branch or full dashboard ([Dashboard](dashboard.md))
- **Change Password** / **Logout**

## Top bar

- **Notification bell** — in-app notifications; open the dropdown to mark all read, clear read items, or enable web push. See [Notifications](notifications.md).
- Brand / logo — returns you toward the main ticket workspace.

## Main ticket list

After login you land on the support tickets list (subject to your role).

- Branch users see only their branch tickets.
- Support agents see department tickets and can filter further as available on the page.
- Announcement cards may appear above the list — see [Announcements](announcements.md).
- Use **+ New Ticket** to create a ticket if your role allows it — see [Creating tickets](creating-tickets.md).

## Suggested next steps

1. Set language and theme in the sidebar.
2. If you are branch staff, [create a ticket](creating-tickets.md).
3. If you are a support agent, [pick a ticket and use the action bar](working-with-tickets.md).
4. Learn [transfer and merge](transfer-and-merge.md) when handing work between agents.
5. Optionally enable [notifications](notifications.md) and browse the [Knowledge Base](knowledge-base.md).

## Related pages

- [Creating tickets](creating-tickets.md)
- [Working with tickets](working-with-tickets.md)
- [Transfer and merge](transfer-and-merge.md)
- [Notifications](notifications.md)
- [Knowledge Base](knowledge-base.md)
- [Announcements](announcements.md)
- [Dashboard](dashboard.md)
