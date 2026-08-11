# Knowledge Base

Browse published help articles, manage drafts when allowed, and link articles to tickets.

**Audience:** Users with Access Knowledge Base (`can_access_kb`); managers with Manage Knowledge Base (`can_manage_kb`).

## Access

Sidebar / navigation includes **Knowledge Base** when your role allows it.

| Permission | What you can do |
|---|---|
| **Access Knowledge Base** (`can_access_kb`) | Open the KB, search and read **published** articles |
| **Manage Knowledge Base** (`can_manage_kb`) | Create/edit/delete articles, work with **drafts**, manage KB categories (via Settings when applicable) |

Superusers have full access.

Open the KB from the sidebar link (**Knowledge Base**). Manage flows appear when you have manage permission (create/edit controls, draft filters, and related UI labeled for managing the Knowledge Base).

## Published vs drafts

- **Published** — visible to anyone with Access Knowledge Base.
- **Drafts** — visible in list/filter to users with Manage Knowledge Base. Save as draft when an article is not ready.

When creating or editing:

1. Enter title, category, and body.
2. Choose save as **draft** or publish (UI actions such as **Save draft** vs publish/save as published).
3. Add attachments if needed.

## Writing articles (TinyMCE)

Article body content is edited with **TinyMCE** (rich HTML). Use headings, lists, and formatting that match your team’s style. Keep steps accurate and short.

## Categories

Articles belong to KB **categories**. Categories (name, description, icon) are managed under **Settings** by users who can manage the KB / settings for categories — not from random ticket screens. Ask an administrator if you need a new category.

## Attachments

KB attachments use the same limits as tickets:

| Rule | Value |
|---|---|
| Maximum size | 10 MB |
| Allowed types | `.pdf`, `.docx`, `.xlsx`, `.jpg`, `.jpeg`, `.png` |

## Related tickets

An article can reference a **related ticket** (the ticket that inspired or is resolved by the article).

Effects you will notice:

- On the ticket **Details** drawer, **Related Knowledge Base Articles** lists linked articles.
- For users with **Access Knowledge Base**, a **published** related KB article grants **cross-scope view** of that ticket: you can view the ticket even when it is outside your normal branch/department org match. This bypass is for viewing (and KB-related discovery), not for unrestricted mutations — pick/chat/status still follow normal org and assignment rules.

Use related tickets when documenting a resolved incident so other KB readers can open context.

## Browse and search (step by step)

1. Open **Knowledge Base**.
2. Filter by category or status (published / draft if you can manage).
3. Search by title or content when the search box is available.
4. Open an article to read, download attachments, and see related articles in the same category.
5. From a ticket’s Details drawer, follow KB links when articles are attached to that ticket.

## Create or edit (managers)

1. From the KB list, start a new article or open an existing one to edit.
2. Set title and category.
3. Optionally set the related ticket (UI may use ticket search / hidden related-ticket field).
4. Write content in TinyMCE.
5. Attach files within size and type limits.
6. Save as draft or publish.

Delete only when you are sure; deleted articles are removed for everyone.

## Related pages

- [Working with tickets](working-with-tickets.md) — Details drawer and related articles
- [Creating tickets](creating-tickets.md) — check KB before opening duplicates
- [Getting started](getting-started.md)
- [Announcements](announcements.md) — short-lived notices vs lasting KB content
