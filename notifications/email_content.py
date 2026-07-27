from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from notifications.utils import format_status_label


def absolute_url(path: str) -> str:
    """Build an absolute URL for email CTAs when SITE_URL is configured."""
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    base = getattr(settings, "SITE_URL", "") or ""
    if not base:
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base.rstrip('/')}{path}"


def static_absolute_url(path: str) -> str:
    """Absolute URL for a static asset path like 'images/logo.png'."""
    from django.templatetags.static import static

    return absolute_url(static(path))


def brand_asset_urls() -> dict[str, str]:
    """Icon + wordmark used in the email header (matches login branding)."""
    return {
        "brand_icon_url": static_absolute_url("images/mlameh-icon-fg.png"),
        # Dark-background wordmark (white lockup) for the indigo header.
        "brand_logo_url": static_absolute_url("images/mlameh-ticket-logo-dark.png"),
    }


def display_name(user) -> str:
    if not user:
        return "Someone"
    full = (user.get_full_name() or "").strip()
    return full or user.username


def truncate_text(value: str, length: int = 500) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return Truncator(text).chars(length, truncate="…")


def format_datetime(value) -> str:
    if not value:
        return "—"
    return timezone.localtime(value).strftime("%b %d, %Y at %H:%M")


def ticket_url(ticket) -> str:
    return absolute_url(f"/tickets/{ticket.id}/")


def ticket_details(ticket) -> list[tuple[str, str]]:
    """Legacy helper kept for tests/callers; not used in the simple email shell."""
    requester = ticket.created_by
    requester_name = display_name(requester) if requester else "—"
    requester_phone = ""
    if requester and requester.phone:
        requester_phone = requester.phone
    elif getattr(ticket, "client_phone", None):
        requester_phone = ticket.client_phone

    assignee = ticket.assigned_to
    priority = (
        ticket.get_priority_display()
        if hasattr(ticket, "get_priority_display")
        else str(ticket.priority)
    )
    status = format_status_label(ticket.status) or ticket.status
    rows = [
        ("Ticket", ticket.ticket_number),
        ("Status", status),
        ("Priority", priority),
        ("Department", ticket.department.name if ticket.department_id else "—"),
        ("Branch", ticket.branch.name if ticket.branch_id else "—"),
        ("Requester", requester_name),
    ]
    if requester_phone:
        rows.append(("Phone", requester_phone))
    if getattr(ticket, "client_name", None):
        rows.append(("Client", ticket.client_name))
    if assignee:
        rows.append(("Assigned to", display_name(assignee)))
    if ticket.category_id:
        rows.append(("Category", ticket.category.name))
    rows.append(("Created", format_datetime(ticket.created_at)))
    return rows


def render_notification_email(
    *,
    body: str,
    cta_url: str = "",
    cta_label: str = "Open in MlamehTicket",
    footer_note: str = "You’re receiving this because email notifications are enabled for your MlamehTicket account.",
    brand_name: str = "MlamehTicket",
) -> tuple[str, str]:
    from notifications.email_templates import body_to_html

    context = {
        "brand_name": brand_name,
        "body": body,
        "body_html": body_to_html(body),
        "cta_url": cta_url,
        "cta_label": cta_label,
        "footer_note": footer_note,
        **brand_asset_urls(),
    }
    html_body = render_to_string("notifications/email/notification.html", context)
    text_body = render_to_string("notifications/email/notification.txt", context)
    text_body = strip_tags(text_body).replace("\r\n", "\n")
    return text_body.strip() + "\n", html_body
