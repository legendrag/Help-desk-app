"""Simple email templates: plain subject/body with {{ token }} merge fields."""

from __future__ import annotations

import re

from django.utils.html import escape

from notifications.email_content import (
    absolute_url,
    display_name,
    format_datetime,
    ticket_url,
    truncate_text,
)
from notifications.utils import format_status_label

BRAND_NAME = "mlamehticket"

TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

# Fields shown as insert buttons in the settings form (per event).
MERGE_FIELDS = {
    "new_ticket": [
        ("brand_name", "Brand"),
        ("ticket_number", "Ticket #"),
        ("title", "Title"),
        ("requester", "Requester"),
        ("department", "Department"),
        ("branch", "Branch"),
        ("priority", "Priority"),
        ("status", "Status"),
        ("description", "Description"),
        ("ticket_url", "Ticket URL"),
    ],
    "ticket_picked": [
        ("brand_name", "Brand"),
        ("ticket_number", "Ticket #"),
        ("title", "Title"),
        ("actor", "Actor"),
        ("status", "Status"),
        ("assignee", "Assignee"),
        ("description", "Description"),
        ("ticket_url", "Ticket URL"),
    ],
    "ticket_message": [
        ("brand_name", "Brand"),
        ("ticket_number", "Ticket #"),
        ("title", "Title"),
        ("actor", "Actor"),
        ("message", "Message"),
        ("ticket_url", "Ticket URL"),
    ],
    "ticket_status": [
        ("brand_name", "Brand"),
        ("ticket_number", "Ticket #"),
        ("title", "Title"),
        ("actor", "Actor"),
        ("status", "Status"),
        ("description", "Description"),
        ("ticket_url", "Ticket URL"),
    ],
    "ticket_update": [
        ("brand_name", "Brand"),
        ("ticket_number", "Ticket #"),
        ("title", "Title"),
        ("actor", "Actor"),
        ("status", "Status"),
        ("description", "Description"),
        ("ticket_url", "Ticket URL"),
    ],
    "transfer_requested": [
        ("brand_name", "Brand"),
        ("ticket_number", "Ticket #"),
        ("title", "Title"),
        ("actor", "Actor"),
        ("description", "Description"),
        ("ticket_url", "Ticket URL"),
    ],
    "transfer_accepted": [
        ("brand_name", "Brand"),
        ("ticket_number", "Ticket #"),
        ("title", "Title"),
        ("actor", "Actor"),
        ("description", "Description"),
        ("ticket_url", "Ticket URL"),
    ],
    "transfer_denied": [
        ("brand_name", "Brand"),
        ("ticket_number", "Ticket #"),
        ("title", "Title"),
        ("actor", "Actor"),
        ("description", "Description"),
        ("ticket_url", "Ticket URL"),
    ],
    "announcement": [
        ("brand_name", "Brand"),
        ("title", "Title"),
        ("content", "Content"),
        ("audience", "Audience"),
        ("expires", "Expires"),
        ("posted_by", "Posted by"),
        ("announcement_url", "URL"),
    ],
}

DEFAULT_TEMPLATES = {
    "new_ticket": {
        "subject": "[{{ brand_name }}] New ticket #{{ ticket_number }}: {{ title }}",
        "body": (
            "New ticket #{{ ticket_number }}\n\n"
            "{{ requester }} submitted a new request for {{ department }}.\n\n"
            "{{ description }}"
        ),
        "cta_label": "View ticket",
    },
    "ticket_picked": {
        "subject": "[{{ brand_name }}] Ticket #{{ ticket_number }} picked up",
        "body": (
            "Ticket #{{ ticket_number }} was picked up\n\n"
            "{{ actor }} is now handling this ticket. Status is {{ status }}.\n\n"
            "{{ description }}"
        ),
        "cta_label": "Open ticket",
    },
    "ticket_message": {
        "subject": "[{{ brand_name }}] New reply on #{{ ticket_number }}",
        "body": (
            "New reply on #{{ ticket_number }}\n\n"
            "{{ actor }} replied to the ticket.\n\n"
            "{{ message }}"
        ),
        "cta_label": "Open ticket",
    },
    "ticket_status": {
        "subject": "[{{ brand_name }}] Status update on #{{ ticket_number }}: {{ status }}",
        "body": (
            "Status changed on #{{ ticket_number }}\n\n"
            "{{ actor }} updated the status to {{ status }}.\n\n"
            "{{ description }}"
        ),
        "cta_label": "Open ticket",
    },
    "ticket_update": {
        "subject": "[{{ brand_name }}] Update on ticket #{{ ticket_number }}",
        "body": (
            "Ticket #{{ ticket_number }} was updated\n\n"
            "{{ actor }} made an update to this ticket.\n\n"
            "{{ description }}"
        ),
        "cta_label": "Open ticket",
    },
    "transfer_requested": {
        "subject": "[{{ brand_name }}] Transfer requested: #{{ ticket_number }}",
        "body": (
            "Transfer requested for #{{ ticket_number }}\n\n"
            "{{ actor }} wants to transfer this ticket to you.\n\n"
            "{{ description }}"
        ),
        "cta_label": "Open ticket",
    },
    "transfer_accepted": {
        "subject": "[{{ brand_name }}] Transfer accepted: #{{ ticket_number }}",
        "body": (
            "Transfer accepted for #{{ ticket_number }}\n\n"
            "{{ actor }} accepted the ticket transfer.\n\n"
            "{{ description }}"
        ),
        "cta_label": "Open ticket",
    },
    "transfer_denied": {
        "subject": "[{{ brand_name }}] Transfer declined: #{{ ticket_number }}",
        "body": (
            "Transfer declined for #{{ ticket_number }}\n\n"
            "{{ actor }} declined the ticket transfer.\n\n"
            "{{ description }}"
        ),
        "cta_label": "Open ticket",
    },
    "announcement": {
        "subject": "[{{ brand_name }}] Announcement: {{ title }}",
        "body": (
            "{{ title }}\n\n"
            "A new announcement has been posted in {{ brand_name }}.\n\n"
            "{{ content }}"
        ),
        "cta_label": "View announcements",
    },
}

EVENT_META = [
    {"event_type": key, "label": label}
    for key, label in [
        ("new_ticket", "New ticket"),
        ("ticket_picked", "Ticket picked"),
        ("ticket_message", "Ticket reply"),
        ("ticket_status", "Status change"),
        ("ticket_update", "Ticket update"),
        ("transfer_requested", "Transfer requested"),
        ("transfer_accepted", "Transfer accepted"),
        ("transfer_denied", "Transfer declined"),
        ("announcement", "Announcement"),
    ]
]


def render_tokens(text: str, context: dict) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        value = context.get(key, "")
        if value is None:
            return ""
        return str(value)

    return TOKEN_RE.sub(repl, text or "")


def ensure_email_templates() -> None:
    from core.models import EmailTemplate

    for event_type, defaults in DEFAULT_TEMPLATES.items():
        EmailTemplate.objects.get_or_create(
            event_type=event_type,
            defaults={
                "subject": defaults["subject"],
                "body": defaults["body"],
            },
        )


def get_template_defaults(event_type: str) -> dict:
    return DEFAULT_TEMPLATES.get(event_type) or DEFAULT_TEMPLATES["ticket_update"]


def resolve_template(event_type: str, context: dict) -> tuple[str, str, str]:
    """Return (subject, body, cta_label) with tokens resolved."""
    from core.models import EmailTemplate

    defaults = get_template_defaults(event_type)
    row = EmailTemplate.objects.filter(event_type=event_type).first()
    subject_src = row.subject if row and row.subject.strip() else defaults["subject"]
    body_src = row.body if row and row.body.strip() else defaults["body"]
    subject = render_tokens(subject_src, context).strip()
    body = render_tokens(body_src, context).strip()
    return subject, body, defaults.get("cta_label") or "Open"


def merge_fields_for_event(event_type: str) -> list[tuple[str, str]]:
    return MERGE_FIELDS.get(event_type) or MERGE_FIELDS["ticket_update"]


def ticket_merge_context(ticket, *, actor=None, message: str = "", status: str | None = None) -> dict:
    status_value = status if status is not None else ticket.status
    status_label = format_status_label(status_value) or (status_value or "")
    priority = (
        ticket.get_priority_display()
        if hasattr(ticket, "get_priority_display")
        else str(getattr(ticket, "priority", "") or "")
    )
    return {
        "brand_name": BRAND_NAME,
        "ticket_number": ticket.ticket_number,
        "title": truncate_text(ticket.title, 80),
        "status": status_label,
        "priority": priority,
        "department": ticket.department.name if ticket.department_id else "",
        "branch": ticket.branch.name if ticket.branch_id else "",
        "requester": display_name(ticket.created_by) if ticket.created_by_id else "",
        "assignee": display_name(ticket.assigned_to) if ticket.assigned_to_id else "",
        "actor": display_name(actor) if actor else "",
        "description": truncate_text(ticket.description, 800) or ticket.title,
        "message": truncate_text(message, 1000),
        "ticket_url": ticket_url(ticket),
    }


def announcement_merge_context(announcement) -> dict:
    if announcement.target_branch_id:
        audience = f"{announcement.target_branch.name} branch"
    else:
        audience = "All users"
    expires = format_datetime(announcement.expires_at) if announcement.expires_at else ""
    return {
        "brand_name": BRAND_NAME,
        "title": truncate_text(announcement.title, 80),
        "content": truncate_text(announcement.content, 1500) or announcement.title,
        "audience": audience,
        "expires": expires,
        "posted_by": display_name(announcement.created_by) if announcement.created_by_id else "",
        "announcement_url": absolute_url("/tickets/"),
    }


def body_to_html(body: str) -> str:
    """Escape plain body text and preserve line breaks for the email shell."""
    return escape(body or "").replace("\n", "<br>\n")


def sample_context_for_event(event_type: str) -> dict:
    """Deterministic sample values for test emails and field demos."""
    sample_url = absolute_url("/tickets/0/") or "/tickets/0/"
    ticketish = {
        "brand_name": BRAND_NAME,
        "ticket_number": "TK-1001",
        "title": "Printer offline in lobby",
        "status": "Open",
        "priority": "High",
        "department": "IT Support",
        "branch": "Main Branch",
        "requester": "Alex Requester",
        "assignee": "Sam Agent",
        "actor": "Sam Agent",
        "description": "The lobby printer shows offline and will not accept jobs.",
        "message": "I restarted it twice; still offline.",
        "ticket_url": sample_url,
    }
    if event_type == "announcement":
        return {
            "brand_name": BRAND_NAME,
            "title": "Office closed Friday",
            "content": "The office will be closed this Friday for maintenance.",
            "audience": "All users",
            "expires": "Jul 31, 2026 at 17:00",
            "posted_by": "Admin User",
            "announcement_url": absolute_url("/tickets/") or "/tickets/",
        }
    if event_type == "ticket_status":
        ticketish["status"] = "In Progress"
    if event_type == "ticket_picked":
        ticketish["status"] = "In Progress"
        ticketish["assignee"] = "Sam Agent"
    return ticketish


def render_subject_body(
    event_type: str,
    subject: str,
    body: str,
    context: dict | None = None,
) -> tuple[str, str, str]:
    """Resolve subject/body strings with context; cta_label from defaults."""
    defaults = get_template_defaults(event_type)
    ctx = context or sample_context_for_event(event_type)
    return (
        render_tokens(subject, ctx).strip(),
        render_tokens(body, ctx).strip(),
        defaults.get("cta_label") or "Open",
    )


def cta_url_for_event(event_type: str, context: dict) -> str:
    if event_type == "announcement":
        return context.get("announcement_url") or ""
    return context.get("ticket_url") or ""
