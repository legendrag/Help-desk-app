# DeskPlus Application - Features & Standards

This document serves as a persistent reference for the features and UI/UX design standards of the DeskPlus Application. It is written to reflect the actual codebase and should be updated as the project evolves.

---

## 🚀 Application Features

### 1. Ticket Lifecycle Management

The ticket is the core entity of the application, managed via `tickets/models.py` and `tickets/template_views.py`.

#### Ticket Fields & Data Model
- **Ticket Number**: Auto-generated on creation using the format `{BRANCH_CODE}-{YYYYMMDD}-{SEQUENCE}` (e.g., `HQ-20260501-0001`). Uses `SELECT FOR UPDATE` to ensure race-condition-safe sequential numbering.
- **Title & Description**: Free-text fields captured during ticket creation.
- **Branch / Department / Category**: Three-level organizational hierarchy. Category options are dynamically loaded via HTMX when a department is selected (`ticket_category_options` endpoint). Categories are validated server-side to belong to the selected department.
- **Priority**: Four levels — `Low`, `Medium`, `High`, `Urgent`.
- **Status**: Five states — `Open`, `In Progress`, `Waiting for Branch`, `Closed`, `Merged`.
- **Assigned To**: Foreign key to a support user. Set automatically when a ticket is picked.
- **Merge Tracking**: A `merged_into` self-referential foreign key marks merged tickets. A full `TicketMergeHistory` log records who merged, when, and which tickets were involved.

#### Time Tracking (Automatic)
The model automatically records and calculates time metrics on save:
- **`picked_at`**: Timestamped when the ticket first transitions to `In Progress`.
- **`closed_at`**: Timestamped when the ticket first transitions to `Closed`.
- **`total_pending_duration_seconds`**: Accumulates total time spent in the `Waiting for Branch` status to exclude idle time from resolution time calculations.
- **`last_status_change_at`**: Updated on every status transition.

These raw timestamps are exposed as calculated metrics on the ticket detail page:
- **Response Time**: `picked_at - created_at`
- **Resolution Time**: `closed_at - picked_at - total_pending_duration_seconds`
- **Time to Close**: `closed_at - created_at`

#### Status History Log
Every status change creates a `TicketStatusHistory` entry, recording the new status, the user who changed it, and the exact timestamp. This is displayed as a full audit trail on the ticket detail page.

---

### 2. Ticket List View & Filtering

Handled by `TicketListView`, paginated at **25 tickets per page**.

- **Search**: Full-text search across `ticket_number`, `title`, and `description` using `icontains` queries.
- **Filter by Branch**: Dropdown filter. Branch users only see their own branch; support users see branches related to their department.
- **Filter by Status**: Dropdown filter across all five status values.
- **Filter by Assignee**: Filter by a specific assigned support agent or show only `Unassigned` tickets.
- **HTMX Live Partial Reload**: When loaded via HTMX, the view returns `tickets/list_live_partial.html` instead of the full page, allowing in-place list refreshes triggered by WebSocket events (e.g., after a ticket is picked or status changes).
- **Scoped Querysets**: Superusers see all tickets; branch users see only their branch's tickets; support users see only their department's tickets.

---

### 3. Ticket Detail View & Chat System

Handled by `TicketDetailView`.

#### Messaging
- **Post Message** (`post_message`): Sends a new message on a ticket. Supports text and a single file attachment per message.
- **Reply Threading**: Messages support a `reply_to` foreign key, enabling threaded conversation display.
- **Edit Message** (`edit_message`): Owners of a message (with the `can_edit_message` role permission) can edit the message text after sending.
- **Delete Message** (`delete_message`): Owners of a message (with the `can_delete_message` role permission) can delete it.
- **Chat Restrictions**:
  - Branch users can only send messages on tickets *they created*.
  - Support users can only send messages on tickets *assigned to them*.
  - Messages cannot be sent on `Closed` or `Merged` tickets (enforced at the model level in `TicketMessage.clean()`).
  - `can_chat` context variable controls whether the message input UI is rendered at all.
- **Keyboard Shortcuts**: The message form is submitted via keyboard shortcut (e.g., `Ctrl+Enter` or `Enter`), without requiring the user to click the send button.

#### File Attachments
- **Drag-and-Drop Upload**: A visual drop-zone overlay activates when a user drags a file over the chat form area, providing clear visual feedback.
- **File Preview Bar**: After selecting a file, an animated preview bar renders below the input showing the filename and a remove button.
- **Storage Path**: Files are stored at `media/tickets/{ticket_id}/{filename}`.

#### Real-Time WebSocket Updates (Django Channels)
All messaging and ticket state events are broadcast instantly via Django Channels (`TicketChatConsumer`). Consumers are scoped to `ticket_{id}` groups.

Events broadcast on the detail page:
| Event Name | Triggered By |
|---|---|
| `message_created` | New message posted |
| `message_deleted` | Message deleted |
| `message_edited` | Message text updated |
| `ticket_status_changed` | Status updated |
| `ticket_picked` | Ticket assigned via "Pick" action |

The list page also receives broadcast events via `ticket_list`, `ticket_list_branch_{id}`, and `ticket_list_department_{id}` groups, allowing it to refresh rows live without polling.

---

### 4. Ticket Actions (Action Bar)

Action buttons displayed on the ticket detail page, each permission-guarded by the user's role:

- **Pick Ticket** (`pick_ticket`): Assigns the ticket to the logged-in support user, sets status to `In Progress`, records the `picked_at` timestamp, creates a `TicketStatusHistory` entry, fires the `notify_ticket_picked` notification, and broadcasts a WebSocket event.
- **Update Status** (`update_ticket_status`): Allows changing the ticket status to any of the five states. Re-opening a closed ticket automatically re-assigns it to the user performing the action.
- **Edit Ticket** (`TicketUpdateView`): Full form to edit ticket fields (branch, department, category, priority, etc.). Uses HTMX partial templates for modal-based in-place editing.
- **Merge Ticket** (`merge_ticket`): See the Ticket Merging section below.

---

### 5. Ticket Merging

A dedicated feature accessible from the ticket detail action bar.

- **Modal UI**: A modal dialog presents a search field for finding the ticket to merge into the current one.
- **HTMX Autocomplete Search** (`ticket_search_options`): As the user types (minimum 2 characters), HTMX fires a request that returns a styled HTML dropdown of matching tickets (by number or title), limited to 15 results. Already-merged tickets are excluded from results.
- **Submit & Confirm**: Once a ticket is selected, the submit button becomes enabled. On confirmation:
  1. The `merge_tickets` service function is called (from `tickets/services.py`).
  2. A `TicketMergeHistory` record is created.
  3. The secondary ticket is set to `Merged` status with a `merged_into` pointer to the primary.
  4. A WebSocket broadcast notifies all clients of the status change on the secondary ticket.
- **Permission Guard**: Only users with `can_update_status` (or superusers) can merge tickets.
- **Data Integrity**: Merging a `Merged` ticket is blocked at the model level. The `merged_into` field is validated to be present when setting status to `Merged`.

---

### 6. Analytics Dashboard

Handled by `DashboardView`. Access is role-gated (`can_access_dashboard`).

- **Scoped Data**: Superusers see all tickets; branch users see only their branch's data; support users see only their department's data.
- **Filterable**: Dashboard data can be filtered by date range (`start_date`, `end_date`), department, branch, and assigned agent.
- **Stat Cards**: Animated cards showing:
  - Total Tickets
  - Total Active Users
  - Active Branches
  - Active Departments
- **Status Breakdown**: Visual horizontal bar chart showing counts and percentages for each status (`Open`, `In Progress`, `Waiting for Branch`, `Closed`, `Merged`).
- **Breakdowns by Category, Department, and Branch**: Each shows a ranked list with relative percentage bars.
- **Date-Series Chart**: Tickets created over time, with **drill-down navigation**:
  - **Year → Month → Week → Day** progressively narrow the period. Drill-up is also supported.
  - Displays the last 7 data points for the selected period granularity.

---

### 7. Notification System

A multi-channel notification system powered by Django Channels, Web Push (service worker), and an async email queue.

#### In-App Notifications
- **Model**: `InAppNotification` stores `title`, `message`, `link`, `notification_type`, `is_read`, and `created_at` per recipient user.
- **WebSocket Push** (`notifications/consumers.py`): Each logged-in user is connected to their own `user_{id}_notifications` WebSocket group. New notifications are pushed instantly without polling.
- **Browser / OS Push**: Delivered via Web Push through the service worker (`sw.js`) when the user has granted notification permission and subscribed. The in-app WebSocket path does not call the native `Notification` API directly.
- **Notification Bell UI**: A bell icon in the topbar shows an unread count badge. Clicking it opens a dropdown panel that fetches the latest 20 notifications via the REST API (`/notifications/api/?limit=20`). Mark-all-read and clear-read are separate header actions (opening the bell does not mark all as read).
- **Auto-Reconnect**: The WebSocket client reconnects automatically after 3 seconds on disconnect, except on auth failure (close code `4401`).
- **On-page suppression**: If the user is already viewing the related ticket page, the live in-app toast is suppressed and the notification is marked read; the service worker similarly suppresses the OS toast when a visible tab is on that ticket URL.

#### Email Notifications (Async Queue)
All email sends are enqueued into a background job queue (`email_queue.py`) rather than sent synchronously, so they never block the HTTP request cycle. Email jobs include:
- `send_new_ticket_email`: Fired when a ticket is created.
- `send_ticket_picked_email`: Fired when a support agent picks a ticket.
- `send_ticket_update_email`: Fired on status changes and message replies (message emails are delayed 120 seconds to reduce noise if the recipient already read the in-app notification).
- `send_transfer_event_email`: Fired on transfer request / accept / deny, to the transfer counterparty.

Email event flags on the active `EmailSetting` gate email only; they do not disable in-app or Web Push notifications.

#### Notification Recipient Logic
- **New Ticket**: Notifies all branch users of the ticket's branch + all support users of the ticket's department + all admins, excluding the ticket creator.
- **Ticket Picked**: Same audience as above, excluding the agent who performed the action.
- **Status Updated**: Same audience, excluding the user who triggered the change (only when the status actually changes).
- **Message Reply**: Notifies creator + assignee + admins when assigned; for unassigned tickets, first message also notifies branch/department users. The actor is always excluded.
- **Transfer request / accept / deny**: Notifies only the transfer counterparty (and emails that same user).

---

### 8. User & Role Management

#### User Model (`accounts/models.py`)
- Extends Django's `AbstractUser`.
- **User Types**: `branch` (needs support) or `support` (support agent).
- **Status**: `Active` or `Inactive`.
- **Linked to**: A `Branch` (for branch users) or a `Department` (for support users).
- **Role**: Foreign key to `core.Role`, which holds a set of granular boolean permissions.
- **Normalized usernames**: Usernames are strip-lowercased on save for consistent handling.

#### Role-Based Permissions (via `core.Role`)
Each role has fine-grained boolean flags controlling access:
| Permission | Controls |
|---|---|
| `can_create_ticket` | Access to ticket creation form |
| `can_update_ticket` | Access to ticket editing |
| `can_update_status` | Status update action + ticket merging |
| `can_pick_ticket` | "Pick" action on unassigned tickets |
| `can_send_message` | Message input on ticket detail |
| `can_edit_message` | Edit own messages |
| `can_delete_message` | Delete own messages |
| `can_update_closed_ticket` | Interact with closed tickets |
| `can_access_dashboard` | Access analytics dashboard |
| `can_access_settings` | Access admin settings panel |

---

### 9. HTMX Integration Patterns

The application uses HTMX extensively to deliver a single-page-app feel without a JavaScript framework.

- **Partial Templates**: Views detect `HX-Request` headers and return lightweight partial templates (e.g., `create_partial.html`, `edit_partial.html`, `list_live_partial.html`) instead of full pages.
- **HX-Trigger Headers**: Server responses send `HX-Trigger` headers to fire client-side events: `closeModal`, `refreshTickets`, `reloadPage`.
- **Dynamic Category Loading**: Selecting a department in the ticket form triggers an HTMX GET to `/tickets/category-options/`, which returns a fresh `<select>` options partial.
- **Merge Search Autocomplete**: The merge modal's search field triggers an HTMX GET to `/tickets/search-options/` with 2-character minimum, returning an inline HTML dropdown without any JavaScript component libraries.

---

### 10. Settings Panel

- Accessible to superusers and users with the `can_access_settings` role permission.
- Provides admin-level controls for managing users, branches, departments, categories, and roles.

---

### 11. Installer & Deployment

- **PowerShell Installer** (`installer/build.ps1`): A packaged installer script to set up the application on Windows environments.
- **Run Script** (`run-deskplus.ps1`): A convenience script to launch the Django development server.
- **Environment Configuration**: Sensitive values (database, email credentials, secret key) are managed via a `.env` file (excluded from git via `.gitignore`).

---

## 🎨 CSS & Design Standards

The application follows a **Premium SaaS / Glassmorphism** design architecture utilizing strictly Vanilla CSS. TailwindCSS or external utility frameworks are avoided in favor of complete design control.

### 1. Architecture & Variable Management
- All modern, high-end styling overrides are located in `static/css/modern.css`. Structural basics are maintained in `style.css`.
- Rely entirely on CSS Custom Properties (`:root`) defined at the top of `modern.css` for colors, border-radii, and shadow tokens.
- **Primary Color Palette**: Uses Indigo (`#4f46e5`) as the primary brand color alongside muted slates for text (`#0f172a`, `#475569`).

### 2. Glassmorphism & Depth
- **Panels & Topbars**: Must utilize semi-transparent backgrounds with `backdrop-filter: blur(24px)` to achieve the frosted glass effect.
- **Borders & Shadows**: Use a subtle white glass border (`1px solid rgba(255, 255, 255, 0.9)`) and deep, soft shadows to create visual hierarchy instead of harsh solid lines.
- **Global Backgrounds**: The body features a premium fixed background utilizing radial gradients to create subtle background glows.

### 3. Interactions & Micro-Animations
- **Subtle Button Hovers**: Buttons should only exhibit subtle background color shifts on hover. *Do not* use "energetic" scaling, popping, or intense drop-shadow transitions. The UI must feel grounded and professional.
- **Smooth Transitions**: Interactive elements (table rows, action bar icons) should use standardized easing transitions: `transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)`.
- **Typing & Loading**: Leverage custom CSS `@keyframes` for smooth typing dot bounces and drop-zone fade-ins.

### 4. Custom Components Standards
- **Dropdowns (Choices.js)**: 
  - Ensure uniform padding, border colors, and rounded corners (`8px` to `12px`).
  - Native dropdown arrows are replaced with custom animated SVG icons that smoothly rotate `-180deg` on open.
  - Ensure the hidden input elements generated by Choices.js are strictly removed from the document flow (`position: absolute; opacity: 0; z-index: -1`) to prevent grid layout jumps.
- **Forms & Grids**: Forms and Modals should enforce rigid CSS Grid layouts that lock columns in place, preventing visual reflows or jumping when error messages or dynamic elements appear.
- **Empty States**: Use consistent, centered, faded typography with large muted emojis/icons to display empty states elegantly.
