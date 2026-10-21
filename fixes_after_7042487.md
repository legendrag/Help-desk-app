# Fixes after round 14 (7042487)

This covers the round 14 bug list. IDs and severities match your report.

Some fixes are in commit 7ccad9c. The rest are in the working tree and will be in the next commit after 7ccad9c. Please test that commit.

## Before you test

1. **Run `migrate`.** There are two new migrations:
   - `accounts.0009_user_language_theme` (per-user language and theme)
   - `notifications.0013_email_outbox` (saved email queue)

   Without them, signed-in pages and email sending fail.
2. **Run `collectstatic`** if you serve from `staticfiles/`. The cache versions are bumped: app-shell.js v16, notifications.js v1.31, chat.js v17, modern.css v3.03.
3. **Language and theme are now saved per user** and follow the user to every device. The language switch and theme toggle save the choice to the account. The first time a user is seen, the account copies the language their browser is already using. When testing Arabic, use the language switch rather than editing the cookie: the saved choice wins over the cookie.

## Fixed

### High
- **BR1. Inactive users showed as Active in the edit form.** The checkbox now reflects the real status, so re-saving no longer turns them back on. (accounts/forms.py)

### Medium
- **B3. Restarting the server lost unsent email.** Fixed in two parts:
  - **Normal stop (7ccad9c):** the server sends the in-memory queue before exiting, including delayed reply emails and retries, for up to 30 s (`EMAIL_QUEUE_SHUTDOWN_SECONDS`).
  - **Crash or forced kill (new):** email jobs are now saved in a database table, `EmailOutbox`, and sent from there. Rows still in the table are sent when the server comes back, after the first request. Two processes never send the same row. A row whose process died mid-send is retried after 15 minutes, so such an email may go out twice but never zero times. Jobs that fail every attempt stay as `failed` in Django admin under "Queued emails", which has a "Retry now" action.
  - I tested a kill: 11 jobs were queued (10 normal plus a delayed reply) and the process was killed without any shutdown code. 0 had been sent, 11 rows survived, and all 11 were sent after the restart.
  - Please re-run your restart test, and also a kill test (`kill -9` / `taskkill /F`).
- **B2. Broken push devices delayed everyone's push.** Three changes:
  - A failing device is skipped for a while after each failure (30 s, doubling up to 1 h). It is removed after 20 failures in a row.
  - The push timeout is now 5 s instead of 10 s.
  - Each user's devices are sent to in parallel.
- **BR2. The rota jumped back to the current week after saving a shift.** The shift dialog now carries the `start` and `view` of the week on screen.
- **BR3. Settings > Users showed only 20 users.** The cap is removed (the other tabs had none), and the list is sorted by username.
- **BR4. The user edit and delete pages showed the edited user as the logged-in user.** The page's variable is now `target_user`, so `user` stays the signed-in user.
- **BR5. "Remove this shift" was missing from the dropdown.** Selects can now opt in to keeping the empty option (`data-allow-empty`), and the edit-shift dialog uses it.
- **BR6 (part). Add shift type didn't pre-fill the department.** It now pre-fills from `?department=`. See "Needs checking in a browser" for the dropdown part.

### Low
- **R13-1. Simultaneous status changes saved and notified twice (7ccad9c).** A conditional update inside a transaction means only one request wins. The other gets "Someone else changed this ticket's status just now". Pick now uses the same protection.
- **B1. A second transfer request within 5 s was dropped.** Transfer request, accept and deny are no longer deduplicated.
- **B14. Websockets accepted connections from other sites when `ALLOWED_HOSTS` is "*".** The new `core/websocket.py` requires the browser's `Origin` to match the socket's `Host`, or a host listed explicitly in `ALLOWED_HOSTS`.
- **B16. Push endpoints whose DNS name points inside the network were accepted.** Endpoints must now be on a known browser push service: fcm.googleapis.com, android.googleapis.com, push.services.mozilla.com, notify.windows.com or push.apple.com. You can override the list with `WEBPUSH_ALLOWED_HOST_SUFFIXES`. Old non-matching subscriptions are deleted instead of being called.
- **NB2. Arabic shift notification titles used a Latin comma.** They now use "،".
- **BR7. Duplicate branch names were accepted.** They're now refused, ignoring case.
- **BR9. Toasts appeared late or piled up.** Two causes, both fixed:
  - When a view reloads the page, its message now shows on the reloaded page instead of in a toast the reload wipes.
  - Faded toasts are now removed from the page, and toast lists are kept out of htmx history snapshots, so going Back no longer replays old toasts.
- **BR10. The live search showed unrelated tickets.** The search form used `hx-sync="this:abort"`, which drops new requests while one is running, so the final keystrokes were lost. It now uses `replace`, and a search also cancels a list refresh still in flight. The dashboard filter forms had the same issue and got the same fix.
- **BR13 / P1-1. The language switch needed a second click or switched back.** The target language and return URL are now read when you click. The switch also resets itself when the browser restores a page from its back/forward cache.
- **BR14. The bell showed only 20 items.** Scrolling to the bottom now loads older ones.
- **BR15. Arabic notification text read jumbled.** Bell titles and messages now get `dir="auto"`.
- **BR18. The 403 page was plain text.** There's now a styled `templates/403.html`. The shifts pages raise PermissionDenied so they use it.
- **BR19 (part). Cancel on the standalone edit page went to the Branches tab.** It now goes back to the right Settings tab, using the new `?tab=` support. The unsaved-changes prompt is not added (see "Left for later").
- **BR20. Delete asked twice.** This affected every `hx-confirm`, not just news delete: the app's dialog confirmed, then htmx asked again with the browser's native confirm. The second prompt is gone.

### UX-minor and part 1
- **U1.** A message that's only spaces now shows "Type a message first."
- **U7.** Live timeline rows use the same "Y-m-d H:i" format as server-rendered rows.
- **U8.** Bell items have an `aria-label` with their title, message and time.
- **U10.** The Add Category department dropdown now shows "Choose a department".
- **U11.** A field's server-side error clears as soon as that field is edited.
- **U12.** The weak-password error now shows under the password field.
- **U14.** The email template field chips are translated into Arabic.
- **P1-2.** Dark mode is written straight into the HTML for signed-in users who chose dark, so the page no longer flashes light first.

## Intentional (not bugs)
- **BR8. The dashboard cards ignore the filters on purpose.** A test pins this (`test_headline_stats_ignore_dashboard_filters`). "Total Users" counts the people who created or were assigned tickets, and "Departments" counts departments that have tickets.
- **U3.** The transfer list shows full name and department without the username, on purpose. Tests pin this format.
- **NB1.** Archiving a shift type doesn't change anyone's shifts. It only removes the type from the picker for new future dates, so there's nothing to notify about.
- **BR17.** No longer applies: the rota's Auto-fill was removed in 28f682a. Bulk assign (Calculator) does the night rotation, with the same Preview then Apply.
- **U6.** A reply on the ticket you're viewing is marked read silently, because you're already looking at it.
- **U12 (part).** Password fields are cleared after a failed submit. That's the standard security default.
- **U14 (part).** Role badges show the role's name as an admin typed it. That's data, not translatable text.
- **Typing in dropdowns does nothing**, on purpose: search is turned off on all TomSelect dropdowns.
- **B5.** Live updates only reach pages connected to the same server process. That's fine with the single Daphne process the app runs. Running more than one process would need Redis.

## Not reproduced: please send details
- **BR11.** A superuser's own messages do get Edit and Delete, in the server-rendered page and in live-added messages. Which account was this?
- **P1-4.** The Arabic greeting string has its space ("مرحباً %(name)s"). A screenshot would help.
- **U13.** The only number in that row is the person's phone, shown as stored. Was that user's phone literally "0"?
- **U9.** "End override" is rendered. It's probably below the fold, since only the modal body scrolls.

## Needs checking in a browser
I couldn't open the app in a browser from here, so please check:
- **BR6:** the shift-type department dropdown ignoring clicks. Nothing in the code explains it; it uses the same setup as the other modal dropdowns.
- **The shared pieces I changed,** since they touch every page:
  - the language switch and the theme toggle, including on a second device
  - toasts after HTMX actions
  - confirmation dialogs, which should now ask only once
  - the ticket search box
  - bell scrolling
  - the 403 page
  - Cancel on the standalone edit pages

## Left for later (owner's decision)
- **B13:** email is still English only. Push and the bell are bilingual.
- **B17:** reply batching.
- **BR12:** Reopen assigns the ticket to whoever reopens it, and doesn't ask for confirmation.
- **BR16 / P1-5:** the header and Settings tables aren't mirrored in right-to-left.
- **BR19 (part):** no unsaved-changes prompt on the standalone edit pages.
- **U2:** the status split button defaults to Close.
- **U4:** the tickets list has no Department or Date filter, and the columns don't sort.
- **U5:** no attachment field on the create-ticket form.
- **U15:** the news feed above the tickets list is long.
