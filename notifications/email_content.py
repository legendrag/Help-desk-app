import logging

from django.conf import settings
from django.template import Context, Engine
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from notifications.email_defaults import (
    DEFAULT_ACCENT_COLOR,
    DEFAULT_BRAND_NAME,
    DEFAULT_FOOTER_NOTE,
)
from notifications.utils import format_status_label

logger = logging.getLogger(__name__)

_TEMPLATE_ENGINE = Engine(autoescape=False)


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


def get_email_appearance():
    """Return the singleton appearance row, or in-memory defaults if missing."""
    from core.models import EmailAppearance

    appearance = EmailAppearance.objects.first()
    if appearance:
        return appearance
    return EmailAppearance(
        brand_name=DEFAULT_BRAND_NAME,
        accent_color=DEFAULT_ACCENT_COLOR,
        footer_note=DEFAULT_FOOTER_NOTE,
    )


def get_email_template(event_type: str):
    """Return an active EmailTemplate for the event, or None."""
    from core.models import EmailTemplate

    return (
        EmailTemplate.objects.filter(event_type=event_type, is_active=True).first()
    )


def render_template_string(template_str: str, context: dict, fallback: str = "") -> str:
    """Render a Django {{ var }} string; on empty/error return fallback."""
    if not template_str or not str(template_str).strip():
        return fallback
    try:
        # Reject control tags — only {{ var }} placeholders are supported.
        if "{%" in template_str or "%}" in template_str:
            raise ValueError("Template tags are not allowed in email copy")
        template = _TEMPLATE_ENGINE.from_string(template_str)
        rendered = template.render(Context(context or {}))
        return rendered if rendered.strip() else fallback
    except Exception as exc:
        logger.warning(
            "Invalid email template string; using fallback. template=%r error=%s",
            template_str,
            exc,
        )
        return fallback


def resolve_email_copy(event_type: str, context: dict, defaults: dict) -> dict:
    """
    Resolve subject/headline/intro/message_title/cta_label from DB templates,
    plus branding from EmailAppearance. Falls back to defaults when needed.
    """
    appearance = get_email_appearance()
    merged_context = {
        **(context or {}),
        "brand_name": appearance.brand_name or DEFAULT_BRAND_NAME,
    }
    tmpl = get_email_template(event_type)

    def field(name: str) -> str:
        raw = getattr(tmpl, name, "") if tmpl else ""
        return render_template_string(raw, merged_context, fallback=defaults.get(name, ""))

    return {
        "subject": field("subject"),
        "headline": field("headline"),
        "intro": field("intro"),
        "message_title": field("message_title"),
        "cta_label": field("cta_label"),
        "brand_name": appearance.brand_name or DEFAULT_BRAND_NAME,
        "accent_color": appearance.accent_color or DEFAULT_ACCENT_COLOR,
        "footer_note": appearance.footer_note or DEFAULT_FOOTER_NOTE,
    }


def ticket_placeholder_context(ticket, actor=None, *, status: str | None = None) -> dict:
    """Build common placeholder context for ticket-related emails."""
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
    appearance = get_email_appearance()
    context = {
        "brand_name": brand_name or appearance.brand_name or DEFAULT_BRAND_NAME,
        "accent_color": accent_color or appearance.accent_color or DEFAULT_ACCENT_COLOR,
        "headline": headline,
        "intro": intro,
        "details": details or [],
        "message_title": message_title,
        "message_body": message_body,
        "cta_url": cta_url,
        "cta_label": cta_label,
        "footer_note": footer_note
        or appearance.footer_note
        or DEFAULT_FOOTER_NOTE,
    }
    html_body = render_to_string("notifications/email/notification.html", context)
    text_body = render_to_string("notifications/email/notification.txt", context)
    # Keep plain text readable even if HTML somehow sneaks into fields.
    text_body = strip_tags(text_body).replace("\r\n", "\n")
    return text_body.strip() + "\n", html_body
