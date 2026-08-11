# Transfer and merge

Hand a ticket to another agent in your department, or merge a secondary ticket into the current primary ticket.

**Audience:** Support Agents (and superusers) who own or manage assigned tickets.

## Overview

| Feature | Purpose |
|---|---|
| **Transfer Ticket** | Ask another same-department agent to take assignment |
| **Merge Ticket** | Fold a secondary ticket into the current (primary) ticket |

Branch (Needs Support) users do not transfer or merge tickets. These controls appear on the ticket detail action bar for the assignee or a superuser.

---

## Transfer Ticket

### Who can transfer

- The agent currently **assigned** to the ticket, or a **superuser**.
- Transfer targets are **same-department** support agents (not the current assignee).
- Transfer is unavailable while a transfer is already pending.

### Request a transfer (step by step)

1. Open the ticket you are assigned to.
2. Open the action bar menu and choose **Transfer Ticket**.
3. In the transfer modal, select the target agent (same department).
4. Confirm **Transfer Ticket**.

A **pending transfer banner** appears on the ticket. The other party is notified (in-app / email / push according to notification settings — see [Notifications](notifications.md)).

### Pending banner actions

| Role | Actions |
|---|---|
| **Target agent** (`pending_transfer_to`) | **Accept** or **Deny** |
| **Requester** (`pending_transfer_by`) or superuser | **Cancel Request** |

Banner text explains who requested the transfer and who must accept.

### Accept

1. Open the ticket (or follow the notification link).
2. On the pending banner, click **Accept**.
3. You become the assignee and can chat and use the full action bar.

### Deny

1. Open the ticket.
2. Click **Deny** on the pending banner.
3. Assignment stays with the original agent; the pending transfer clears. The requester is notified.

### Cancel Request

1. As the agent who started the transfer (or as superuser), open the ticket.
2. Click **Cancel Request** on the pending banner.
3. The pending transfer clears; the target is notified as configured.

### Transfer rules summary

- Same department only.
- One pending transfer at a time (menu hides **Transfer Ticket** while pending).
- Notifies the counterparty on request, accept, deny, and cancel flows.

---

## Merge Ticket

Merge moves conversation from a **secondary** ticket **into** the **current** ticket (the primary). The secondary ticket becomes **Merged**.

### Who can merge

- UI is available to the **assignee** or a **superuser** via **Merge Ticket** on the action bar.
- The operation requires permission to update status (`can_update_status`) as enforced by the app.
- You cannot merge into a **Closed** ticket.

### What merge does

- Moves messages from the secondary ticket to the primary.
- Marks the secondary ticket **Merged**, with a merged banner / relation to the primary.
- Upgrades the primary ticket’s **priority** if the secondary’s priority is higher.
- Records system history / messages noting the merge.
- Clears any pending transfer on the secondary ticket.

Merge into the current primary is irreversible from the user’s perspective — confirm the secondary ticket number carefully.

### Merge step by step

1. Open the ticket that should remain as the **primary** (the ticket you are viewing).
2. Ensure it is not **Closed**.
3. From the action bar, choose **Merge Ticket**.
4. In the merge modal, identify the **secondary** ticket (by number / search as the UI provides).
5. Review the preview (messages will move into this ticket; the secondary will be marked Merged).
6. Confirm **Merge Ticket**.

Afterward:

- Continue work on the primary ticket.
- Open the secondary only to see the merged state / banner pointing at the primary.
- Branch users continue chatting on the primary if it is in their branch — [Working with tickets](working-with-tickets.md).

### Merge restrictions

| Rule | Detail |
|---|---|
| Direction | Secondary **into** current primary |
| Closed primary | Not allowed |
| Already merged | Cannot use an already-merged ticket as a normal merge target/source as the service validates |
| Permissions | Needs status-update capability; UI for assignee/superuser |
| Priority | Primary priority upgrades if secondary is higher |

---

## Choosing transfer vs merge

- **Transfer** when the same ticket should keep its number and history, but another agent should own it.
- **Merge** when two tickets are duplicates or the same incident and you want one conversation thread under the primary number.

## Related pages

- [Working with tickets](working-with-tickets.md) — action bar, chat, statuses
- [Getting started](getting-started.md) — roles and ticket numbers
- [Notifications](notifications.md) — transfer alerts
- [Dashboard](dashboard.md) — volume after merges still counts under how reporting is built
