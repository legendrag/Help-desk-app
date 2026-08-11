# Dashboard

View branch or full-organization ticket metrics, charts, and Excel export.

**Audience:** Users with Access Dashboard (`can_access_dashboard`); Agent Performance / leaderboard needs View Agent Leaderboard (`can_view_leaderboard`) where noted.

## Access

You need **Access Dashboard** on your role (or superuser). The sidebar shows **Dashboard** when allowed.

What you get depends on user type:

| User type | Dashboard |
|---|---|
| Needs Support (`branch`) | **Branch Dashboard** — metrics for your branch |
| Support Agent (`support`) | Full **Dashboard** — department/organization views, filters, and Excel export |

## Branch Dashboard

Branch users open **Branch Dashboard** to see activity for their location: status summaries, request activity by date, and related branch-scoped widgets provided on that page.

Use it to understand open volume and waiting tickets for your branch. Creating and chatting on tickets remains on the ticket list and detail pages — [Working with tickets](working-with-tickets.md).

## Full Dashboard (support)

Support agents (with dashboard access) open the full **Dashboard**.

Typical capabilities:

- Filter by the same kinds of dimensions available on the page (dates, status, assignment, branch, and similar query filters).
- Review ticket volume and status breakdowns.
- Use the **volume trend** chart; zoom the chart as the UI allows to focus on a date range.
- View **Agent Performance** / leaderboard tables when your role includes **View Agent Leaderboard** (`can_view_leaderboard`).
- **Export Excel** — download a workbook for the current filter set.

### Excel export sheets

Click **Export Excel**. The file includes sheets:

| Sheet | Contents |
|---|---|
| **Tickets** | Ticket-level rows for the filtered set |
| **Agent Performance** | Agent metrics |
| **Status Summary** | Counts by status |
| **Departments** | Status breakdown by department |
| **Categories** | Status breakdown by category |
| **Branches** | Status breakdown by branch |

The download name follows a pattern such as `dashboard_export_YYYYMMDDHHMM.xlsx`. Filters in the URL/query string apply to the export.

## Volume trend

Both dashboards that include the volume chart show ticket (or request) activity over time. Use chart zoom/controls in the UI to inspect peaks without changing the underlying ticket data.

## Agent Performance

The Agent Performance / leaderboard block appears when you have **`can_view_leaderboard`**. Without that permission, other dashboard sections may still load, but leaderboard-style agent ranking is withheld.

## How to use the dashboard (step by step)

1. Confirm your role has dashboard access; open **Dashboard** from the sidebar.
2. If you are Needs Support, review the **Branch Dashboard** stats for your location.
3. If you are Support, set filters for the period and scope you care about.
4. Inspect status summaries and the volume trend (zoom as needed).
5. If permitted, review Agent Performance.
6. Click **Export Excel** when you need an offline report for leadership or audits.

## Related pages

- [Getting started](getting-started.md) — roles and permissions overview
- [Working with tickets](working-with-tickets.md) — live queue behind the metrics
- [Transfer and merge](transfer-and-merge.md) — how merges affect ticket counts
- [Announcements](announcements.md) — notices above the ticket list, not on the dashboard itself
