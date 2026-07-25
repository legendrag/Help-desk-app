from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from notifications.email_messages import (
    DEFAULT_ACCENT_COLOR,
    DEFAULT_BRAND_NAME,
    DEFAULT_FOOTER_NOTE,
    get_email_brand,
)
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


def ticket_placeholder_context(ticket, actor=None, *, status: str | None = None) -> dict:
    department = ticket.department.name if ticket.department_id else ""
    status_label = status
    if status_label is None:
        status_label = format_status_label(ticket.status) or ticket.status
    actor_user = actor if actor is not None else ticket.created_by
    return {
        "ticket_number": ticket.ticket_number,
        "ticket_title": truncate_text(ticket.title, 80),
        "actor_name": display_name(actor_user),
        "status": status_label or "",
        "department": department,
        "department_suffix": f" for {department}" if department else "",
    }


def render_notification_email(
    *,
    headline: str,
    intro: str,
    details: list[tuple[str, str]] | None = None,
    message_title: str = "",
    message_body: str = "",
    cta_url: str = "",
    cta_label: str = "Open in mlamehticket",
    footer_note: str = "",
    brand_name: str = "",
    accent_color: str = "",
) -> tuple[str, str]:
    brand = get_email_brand()
    context = {
        "brand_name": brand_name or brand.brand_name or DEFAULT_BRAND_NAME,
        "accent_color": accent_color or brand.accent_color or DEFAULT_ACCENT_COLOR,
        "headline": headline,
        "intro": intro,
        "details": details or [],
        "message_title": message_title,
        "message_body": message_body,
        "cta_url": cta_url,
        "cta_label": cta_label,
        "footer_note": footer_note or brand.footer_note or DEFAULT_FOOTER_NOTE,
    }
    html_body = render_to_string("notifications/email/notification.html", context)
    text_body = render_to_string("notifications/email/notification.txt", context)
    # Keep plain text readable even if HTML somehow sneaks into fields.
    text_body = strip_tags(text_body).replace("\r\n", "\n")
    return text_body.strip() + "\n", html_body
