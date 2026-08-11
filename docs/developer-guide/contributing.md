# Contributing

Conventions for changing mlamehticket so new work matches the existing SSR + HTMX + vanilla CSS stack.

**Audience:** Developers submitting code or template/CSS changes.

## Read first

- Product and UI expectations: [`../../PROJECT_STANDARDS.md`](../../PROJECT_STANDARDS.md)
- Architecture snapshot: [architecture.md](architecture.md)
- Permissions: [permissions-and-scoping.md](permissions-and-scoping.md)

### Stale notes in `PROJECT_STANDARDS.md`

Treat that file as useful feature context, but verify against code when details conflict. Known drift:

- **Role permission count** — the doc’s permission table is incomplete; `core.Role` currently exposes on the order of ~31 boolean flags (not a short dozen).
- **Dropdown library** — the standards doc still mentions **Choices.js**; the live UI loads **Tom Select** from CDN (`templates/base.html`). Prefer Tom Select patterns when touching selects.
- Chat send rules and other UX bullets may lag `tickets/access.py` / consumers — trust the code for authorization.

## Stack conventions

| Do | Don’t |
|---|---|
| Django templates + HTMX partials | Add a React/Vue SPA for core flows |
| Vanilla CSS in `static/css/` (`modern.css`, `style.css`, `rtl.css`, …) | Introduce **Tailwind** or utility-framework CSS |
| Vanilla JS in `static/js/` (+ Tom Select / Chart.js where already used) | Add large front-end frameworks without an explicit project decision |
| Channels events for live updates | Poll when a group broadcast already exists |
| In-process `email_queue` for mail | Assume Celery/Redis are available |

## HTMX conventions

- Detect `HX-Request` and return **partial** templates when the full chrome is unnecessary (`*_partial.html`, list live partials, drawers).
- Prefer server-driven UI: return HTML fragments, not JSON, for progressive enhancement.
- Use response headers such as `HX-Trigger` for cross-component actions (`closeModal`, refresh list, reload) when that pattern already exists nearby.
- Keep category and merge search endpoints returning option/dropdown HTML fragments.
- Language is cookie-based — do not invent `/ar/` URL prefixes for HTMX targets.

## Templates and i18n

- Wrap user-facing copy with `{% trans %}` / `{% blocktrans trimmed %}` / gettext in Python.
- Always include **`trimmed`** on `blocktrans`.
- After string changes: `python scripts/i18n.py update` → translate → `compile` → `check --verbose`. See [i18n.md](i18n.md).

## CSS

- Extend existing tokens and components in `static/css/modern.css` (and related files).
- Preserve glass/panel patterns already in the shell; avoid one-off inline style sprawl for reusable chrome.
- Respect RTL via existing `rtl.css` rather than hard-coding left/right in new features when directional helpers exist.

## Python / Django

- New ticket authorization: use `tickets.access` helpers; do not widen KB bypass into mutations.
- Prefer existing apps (`tickets`, `core`, `notifications`, …) over new top-level packages.
- Do not add Redis/Celery “because production scale” without an explicit architecture change — current design is in-memory Channels + thread email queue.
- Keep installer packaging changes inside `installer/`.

## Formatting / lint

Dev extras include **djlint** (see `requirements-dev.txt`) for Django template formatting/linting. Use it when editing templates so markup stays consistent with the rest of the tree.

```bash
pip install -r requirements-dev.txt
# Example — adjust paths/flags to match team practice:
djlint templates --check
```

## Tests

- Add Django `TestCase` coverage for tenancy and permission changes.
- Run `python manage.py test` (and `test-local.ps1` when available).
- Details: [testing.md](testing.md).

## Documentation

- User/operator docs live under `docs/user-guide/`, `docs/admin-guide/`, `docs/operations/`.
- Developer docs live here under `docs/developer-guide/`.
- Prefer updating the relevant markdown when behavior changes in a user-visible or contributor-visible way.

## Related docs

- [Project structure](project-structure.md)
- [URL reference](url-reference.md)
- [Realtime](realtime.md)
