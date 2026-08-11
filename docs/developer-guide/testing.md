# Testing

How the Django test suite is organized, how to run it, and what is intentionally stubbed.

**Audience:** Developers adding or running automated tests.

## Framework

mlamehticket uses **Django’s `TestCase`** (and related Django test tools). It does **not** use pytest as the project test runner.

```bash
python manage.py test
```

Or use the local helper script `test-local.ps1` (runs tests and i18n check).

## Migrations during tests

When `manage.py` is invoked with `test` in `sys.argv`, `config.settings` installs a `MIGRATION_MODULES` stub that disables migrations for speed. Schema is created from models instead.

Do not assume migration-only data transforms run inside the test database bootstrap.

## Coverage by app

| App | Status | Focus |
|---|---|---|
| `accounts` | Tests present | Superadmin bootstrap / weak password guards; logout clears webpush |
| `tickets` | Tests present | System messages, authz views, list search, XSS/upload hardening, tenancy + KB bypass |
| `notifications` | Tests present | Announcement recipients, email content/templates/test-send, new-ticket in-app |
| `kb` | Tests present | Browse/search UI polish, attachments helpers, partials |
| `core` | Stub only | Placeholder `TestCase` file |
| `news` | Stub only | Placeholder `TestCase` file |

There are on the order of **~56** `test_*` methods across the real suites (`tickets` holds most of them).

## Notable scenarios already covered

- Ticket detail/edit authorization for branch vs support tenancy
- KB view bypass: published related article + `can_access_kb` allows HTTP view; denied without the flag; pick/reopen remain org-scoped
- Attachment allow/deny by extension; message HTML escaped in detail
- List search by client name, phone digits, assignee; HTMX load-more partial
- Notification audience for global vs branch announcements
- Email rendering and custom `EmailTemplate` override paths (SMTP send mocked)

When fixing a permissions bug, prefer extending `tickets.tests.SecurityTenancyTests` or a sibling class rather than inventing a parallel framework.

## Writing new tests

1. Put tests in the app’s `tests.py` (or split modules later if a file grows large).
2. Use Django’s test client for HTTP; patch email enqueue / channel broadcast where side effects are noisy.
3. Build users with explicit `user_type`, `branch` / `department`, and `role` flags — tenancy bugs hide behind incomplete fixtures.
4. Keep tests independent of real SMTP, Redis, or multi-process Channels behavior.

Example pattern:

```python
from django.test import TestCase
from django.urls import reverse


class ExampleTests(TestCase):
    def test_branch_user_cannot_see_other_branch(self):
        self.client.force_login(self.other_branch_user)
        response = self.client.get(reverse("ticket_detail", args=[self.ticket.id]))
        self.assertEqual(response.status_code, 404)  # or whatever the view returns
```

(Adjust assertions to match the view under test.)

## Related docs

- [Permissions and scoping](permissions-and-scoping.md)
- [i18n](i18n.md) (`check` is part of local quality gates)
- [Contributing](contributing.md)
