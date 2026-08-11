# Announcements

Read dismissible announcement cards above the ticket list, scoped by branch or global.

**Audience:** All users who use the ticket list; authors who create announcements in the news/announcements admin UI.

## Where announcements appear

Active, non-expired announcements show as **cards above the ticket list**. They are separate from the notification bell, though creating an announcement can also notify users — see [Notifications](notifications.md).

## Targeting

| Target | Who sees the card |
|---|---|
| **Global** (no target branch) | Branch users and support agents |
| **Branch** (`target_branch` set) | Needs Support users of that branch (and superusers as applicable) |

**Support agents see only global announcements** on the ticket list. Branch-targeted cards are for the matching branch audience, not for agents browsing the department queue.

Inactive or expired announcements do not appear.

## Expiration

Each announcement may set **`expires_at`**. After that date and time, the card hides automatically even if it remains marked active in admin.

Leave expiration empty for an announcement that stays until someone deactivates or dismisses it locally.

## Dismiss (localStorage)

Cards are **dismissible**. When you dismiss an announcement:

- It hides for you in that browser.
- The choice is stored in **`localStorage`** (per announcement id).
- Other users still see it.
- Clearing site data or using another browser/device can show it again.

Dismiss is a personal UI preference, not a server-wide “mark read” for everyone.

## Reading announcements (step by step)

1. Open the ticket list.
2. Read any cards above the list.
3. Follow links or instructions in the content if provided.
4. Dismiss the card when you no longer need it on that device.
5. Check the [notification bell](notifications.md) if you were away when the announcement was published.

## Creating announcements (authors)

If your role includes announcement management (news/announcements screens):

1. Create a new announcement with title and content.
2. Choose **target branch** or leave blank for **global**.
3. Set **expires_at** (date/time) if the notice should auto-hide.
4. Mark it active and save.

Prefer **global** for messages all agents must see. Use **branch** targeting for location-specific notices to Needs Support users.

## Announcements vs Knowledge Base

| | Announcements | Knowledge Base |
|---|---|---|
| Purpose | Short-lived operational notices | Lasting how-to / reference articles |
| Placement | Cards above ticket list | KB section |
| Persistence | Expiry + dismiss | Published drafts/articles |
| Docs | This page | [Knowledge Base](knowledge-base.md) |

## Related pages

- [Getting started](getting-started.md)
- [Working with tickets](working-with-tickets.md) — ticket list context
- [Notifications](notifications.md)
- [Knowledge Base](knowledge-base.md)
