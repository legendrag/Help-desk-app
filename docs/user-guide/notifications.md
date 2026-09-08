# Notifications

Use the bell, email, and optional web push to stay current on tickets and announcements.

**Audience:** All signed-in branch and support users.

## Where notifications appear

### Bell in the top bar

The notification **bell** sits in the top bar. The badge shows how many unread items you have. Click the bell to open the dropdown.

Inside the dropdown you can:

- Browse recent notifications (ticket events, transfers, announcements, and similar types).
- Open a notification to jump to the related ticket or content when a link is provided.
- **Mark all as read** — marks every notification as read.
- **Clear read** — removes notifications that are already read from the list.
- **Enable** web push — shown when the browser can subscribe; see below.

Empty state: **No notifications yet**.

### Notifications-off banner

When browser notifications are not granted, a banner appears at the top of every signed-in page:

- **Notifications are off** — with **Turn on** to request permission (or to show how to unblock them if the browser already blocked the site).
- **X** dismisses the banner for this browser. You can still enable push from the bell dropdown.

If notifications are blocked, **Turn on** opens a short guide that depends on how you are using the app:

- **Browser tab** — use the site-settings icon next to the address bar and turn Notifications on.
- **Installed app** — open this app’s notification settings on the device and turn Notifications on.
- **iPhone or iPad in Safari** — web push needs a Home Screen install first. Open the Share menu, tap **Add to Home Screen**, then open the app from there to turn notifications on.

The banner hides itself once permission is granted.

### On-page toast

When a new event arrives while you are using the app, a toast may appear. If you are **already viewing that ticket** (the ticket detail chat URL), the on-page toast for that ticket is **suppressed** so you are not interrupted while reading the same conversation. List pages (including announcements on the ticket list) still allow toasts.

### Email

Email notifications depend on administrator Email Settings (SMTP and event toggles). When enabled for your events:

- Most events can send promptly according to server configuration.
- **Message** (chat reply) emails are **delayed about 120 seconds** so rapid back-and-forth does not flood your inbox.

### Web push

Web push delivers OS-level notifications when the app is in the background (browser and device permitting).

1. If the **Notifications are off** banner is visible, click **Turn on** and allow the prompt (or follow the guide if notifications are blocked).
2. Or open the notification dropdown and click **Enable**.
3. **Browser tab:** if the site is blocked, use the site-settings icon next to the address bar.
4. **Installed app:** if notifications are blocked, turn them on in this app’s device settings.
5. **iPhone or iPad in Safari:** add the app to the Home Screen first, then open it from there and turn notifications on.

Browsers require a user gesture to grant permission; use **Turn on** or **Enable** rather than expecting a silent subscribe on page load.

## Duplicate suppression

Identical notifications are suppressed for **60 seconds**. If the same title and message would be created again within that window, the duplicate is skipped (in-app, and related push/email paths that share that creation). This reduces noise from repeated identical events.

## Typical notification types

You may see events such as:

- New ticket
- Ticket picked
- New chat message
- Status change
- Ticket update
- Transfer requested / accepted / declined
- Announcement

Exact wording follows the templates configured by administrators.

## Recommended setup

1. Keep the bell visible while working tickets.
2. Click **Turn on** on the banner (or **Enable** in the bell) for web push on devices you use for support.
3. Confirm with an administrator that email is configured if you expect inbox alerts.
4. Use **Mark all as read** at the end of a shift; use **Clear read** to tidy the dropdown.

## Related pages

- [Getting started](getting-started.md) — login and sidebar
- [Working with tickets](working-with-tickets.md) — events that trigger alerts
- [Transfer and merge](transfer-and-merge.md) — transfer notifications
- [Announcements](announcements.md) — announcement cards and alerts
