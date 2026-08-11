# mlamehticket documentation

**Audience:** Everyone — start here and follow the link for your role.

English documentation for the mlamehticket help-desk platform. Pick the section that matches what you need to do.

## By audience

| Audience | Start here | Covers |
|---|---|---|
| Branch staff & support agents | [User guide](user-guide/getting-started.md) | Login, tickets, chat, transfer/merge, notifications, KB, announcements, dashboard |
| In-app administrators | [Admin guide](admin-guide/settings-hub.md) | Settings Hub, users & roles, organization, email, maintenance |
| Operators / deployers | [Operations](operations/installation.md) | Install, configure, deploy, backup, security, troubleshooting |
| Developers / contributors | [Developer guide](developer-guide/architecture.md) | Architecture, data model, URLs, realtime, i18n, testing |
| Quick lookups | [Reference](reference/glossary.md) | Glossary, permissions matrix, management commands |

## Common tasks

| Task | Doc |
|---|---|
| Run locally for the first time | [Installation](operations/installation.md) |
| Configure `.env` | [Configuration](operations/configuration.md) |
| Deploy with MySQL + Daphne | [Deployment](operations/deployment.md) |
| Set up Gmail for notification emails | [Gmail app password](admin-guide/gmail-app-password.md) |
| Back up / restore the database | [Backup & restore](operations/backup-restore.md) |
| Understand roles and permissions | [Users and roles](admin-guide/users-and-roles.md) · [Permissions matrix](reference/permissions-matrix.md) |
| Add or update Arabic translations | [i18n](developer-guide/i18n.md) |
| Run the test suite | [Testing](developer-guide/testing.md) |

## Project overview

mlamehticket is a Django monolith for branch help-desk tickets. Branch users (Needs Support) open tickets; support agents pick, chat, transfer, merge, and close them. Real-time chat and notifications use Django Channels. The UI is Django Templates + HTMX + vanilla CSS/JS, with English and Arabic (cookie-based language, no URL prefixes).

For a short project summary and quick-start commands, see the root [README.md](../README.md).
