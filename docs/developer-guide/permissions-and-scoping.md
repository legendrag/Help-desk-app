# Permissions and scoping

How authentication, role flags, middleware, and ticket queryset rules combine — including the knowledge-base view bypass.

**Audience:** Developers adding views, APIs, or WebSocket checks that must respect tenancy and roles.

## Authentication stack

| Piece | Behavior |
|---|---|
| `AUTH_USER_MODEL` | `accounts.User` |
| Backend | `accounts.backends.CaseInsensitiveModelBackend` — username `__iexact` |
| `LOGIN_URL` | `login` |
| Session | Cookie session; age configurable (`SESSION_COOKIE_AGE`, default 3 days) |

Inactive Django `is_active` still follows ModelBackend’s `user_can_authenticate`. Product “active” status is also modeled on `User.status` (`active` / `inactive`) and used in notification recipient filters.

## Middleware gates

After standard Django auth middleware:

1. **`NoCacheAfterLogoutMiddleware`** — authenticated responses get never-cache headers.
2. **`ForcePasswordChangeMiddleware`** — if `requires_password_change`, only `password_change`, `logout`, `/static/`, `/media/`, and `/admin/` are allowed; everything else redirects to password change.

These are not substitutes for object-level ticket checks.

## Role flags (`core.Role`)

Users optionally point at a `Role` with boolean permissions (~31 flags), including:

- Tickets: create/update/pick/status/closed-status, send/edit/delete message
- Dashboard / leaderboard / settings access
- Settings CRUD: users, branches, departments, categories, roles
- `can_manage_email`, `can_manage_news`, `can_access_kb`, `can_manage_kb`, `can_manage_maintenance`

A role named `admin` (case-insensitive) forces all booleans true on save. Superusers bypass many checks independently of role.

Views typically combine:

- `user.is_superuser`, and/or
- `user.role.<flag>` when `role_id` is set.

Missing role usually means denied for privileged actions.

## Tenancy model

| `user_type` | Org anchor | Default ticket visibility |
|---|---|---|
| `branch` | `user.branch_id` | Tickets with matching `ticket.branch_id` |
| `support` | `user.department_id` | Tickets with matching `ticket.department_id` |
| Superuser | — | All tickets |

List and dashboard querysets in `tickets.template_views` apply that filter for non-superusers. Branch users creating tickets normally have branch locked to their own.

## Shared helpers (`tickets/access.py`)

### `user_in_ticket_org(user, ticket)`

Strict match: same branch (branch users) or same department (support users). Superuser always true. **No KB bypass.** Used for mutations and WebSocket chat access.

### `user_can_view_ticket(user, ticket)`

Returns true if:

1. Superuser, or
2. `user_in_ticket_org`, or
3. **KB bypass:** `user.role.can_access_kb` **and** the ticket has at least one **published** related KB article (`ticket.kb_articles.filter(is_published=True)`).

Detail/drawer HTTP views use `user_can_view_ticket`. Chat WebSocket uses **only** `user_in_ticket_org`, so KB bypass is view-only over HTTP.

### `user_can_pick_ticket` / `user_can_reopen_ticket`

Require org match first. Pick also requires unassigned, not merged, and `can_pick_ticket` (unless superuser). Reopen allows same-org support users (or `can_update_closed_ticket` / superuser).

## Practical rules of thumb

| Action | Check |
|---|---|
| List tickets | Queryset scoped by branch/department (or all if superuser) |
| View ticket HTML | `user_can_view_ticket` (KB bypass possible) |
| Edit / status / merge / transfer / post with attachment via HTTP | Org + role flags (and assignee rules where coded) |
| Live chat subscribe / WS send | `user_in_ticket_org` only; support send also requires assignee |
| Pick | `user_can_pick_ticket` |
| Settings / maintenance / user admin | Role flags such as `can_access_settings`, `can_manage_maintenance`, CRUD flags |
| KB browse | `can_access_kb`; manage articles/categories needs `can_manage_kb` (as enforced in KB views) |

When adding a new mutating endpoint, prefer `user_in_ticket_org` (or a helper that calls it). Do not reuse `user_can_view_ticket` alone for writes — that would widen KB bypass into mutations.

## Related docs

- [Data model](data-model.md)
- [Realtime](realtime.md)
- [Architecture](architecture.md)
- [Testing](testing.md) (tenancy / KB bypass coverage)
