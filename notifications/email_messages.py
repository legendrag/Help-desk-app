"""Email designer: brand/message loading, tokens, and merge-field chips."""

from __future__ import annotations

import logging
import re
from html import escape, unescape

from django.template import Context, Engine

logger = logging.getLogger(__name__)

_TEMPLATE_ENGINE = Engine(autoescape=False)

DEFAULT_BRAND_NAME = "mlamehticket"
DEFAULT_ACCENT_COLOR = "#4f46e5"
DEFAULT_PAGE_BACKGROUND = "#f8fafc"
DEFAULT_CARD_BACKGROUND = "#ffffff"
DEFAULT_TABLE_HEADER_BG = "#f8fafc"
DEFAULT_TABLE_BORDER_COLOR = "#e2e8f0"
DEFAULT_TEXT_COLOR = "#0f172a"
DEFAULT_MUTED_TEXT_COLOR = "#64748b"
DEFAULT_TABLE_LAYOUT = "classic"
DEFAULT_TABLE_FILL_MODE = "striped"
DEFAULT_TABLE_RADIUS = 12
DEFAULT_TABLE_ROW_PADDING_Y = 10
DEFAULT_TABLE_ROW_PADDING_X = 14
DEFAULT_TABLE_LABEL_WIDTH = 38
DEFAULT_FOOTER_NOTE = (
    "You’re receiving this because email notifications are enabled "
    "for your mlamehticket account."
)

TABLE_LAYOUT_DEFAULTS = {
    "classic": {
        "table_radius": 12,
        "table_row_padding_y": 10,
        "table_row_padding_x": 14,
        "table_label_width": 38,
        "table_show_outer_border": True,
        "table_show_row_dividers": True,
        "table_fill_mode": "striped",
    },
    "compact": {
        "table_radius": 8,
        "table_row_padding_y": 6,
        "table_row_padding_x": 10,
        "table_label_width": 34,
        "table_show_outer_border": True,
        "table_show_row_dividers": True,
        "table_fill_mode": "striped",
    },
    "minimal": {
        "table_radius": 0,
        "table_row_padding_y": 8,
        "table_row_padding_x": 0,
        "table_label_width": 36,
        "table_show_outer_border": False,
        "table_show_row_dividers": True,
        "table_fill_mode": "none",
    },
    "pills": {
        "table_radius": 18,
        "table_row_padding_y": 10,
        "table_row_padding_x": 14,
        "table_label_width": 38,
        "table_show_outer_border": False,
        "table_show_row_dividers": False,
        "table_fill_mode": "labels",
    },
}

BRAND_SURFACE_DEFAULTS = {
    "page_background": DEFAULT_PAGE_BACKGROUND,
    "card_background": DEFAULT_CARD_BACKGROUND,
    "table_header_bg": DEFAULT_TABLE_HEADER_BG,
    "table_border_color": DEFAULT_TABLE_BORDER_COLOR,
    "text_color": DEFAULT_TEXT_COLOR,
    "muted_text_color": DEFAULT_MUTED_TEXT_COLOR,
    "table_layout": DEFAULT_TABLE_LAYOUT,
    "table_fill_mode": DEFAULT_TABLE_FILL_MODE,
    "table_radius": DEFAULT_TABLE_RADIUS,
    "table_row_padding_y": DEFAULT_TABLE_ROW_PADDING_Y,
    "table_row_padding_x": DEFAULT_TABLE_ROW_PADDING_X,
    "table_label_width": DEFAULT_TABLE_LABEL_WIDTH,
    "table_show_outer_border": True,
    "table_show_row_dividers": True,
}

EVENT_META = [
    {
        "event_type": "new_ticket",
        "label": "New ticket",
        "purpose": "Sent when someone opens a request",
        "group": "ticket",
    },
    {
        "event_type": "ticket_picked",
        "label": "Ticket picked",
        "purpose": "Sent when an agent picks up a ticket",
        "group": "ticket",
    },
    {
        "event_type": "ticket_message",
        "label": "Reply",
        "purpose": "Sent when there is a new ticket reply",
        "group": "ticket",
    },
    {
        "event_type": "ticket_status",
        "label": "Status change",
        "purpose": "Sent when ticket status changes",
        "group": "ticket",
    },
    {
        "event_type": "ticket_update",
        "label": "Ticket update",
        "purpose": "Sent for general ticket updates",
        "group": "ticket",
    },
    {
        "event_type": "transfer_requested",
        "label": "Transfer requested",
        "purpose": "Sent when a transfer is requested",
        "group": "ticket",
    },
    {
        "event_type": "transfer_accepted",
        "label": "Transfer accepted",
        "purpose": "Sent when a transfer is accepted",
        "group": "ticket",
    },
    {
        "event_type": "transfer_denied",
        "label": "Transfer declined",
        "purpose": "Sent when a transfer is declined",
        "group": "ticket",
    },
    {
        "event_type": "announcement",
        "label": "Announcement",
        "purpose": "Sent when a news announcement is posted",
        "group": "announcement",
    },
]

TICKET_MERGE_FIELDS = [
    {"key": "brand_name", "label": "App name", "sample": "mlamehticket"},
    {"key": "ticket_number", "label": "Ticket number", "sample": "TK-1042"},
    {"key": "ticket_title", "label": "Ticket title", "sample": "Printer offline"},
    {"key": "actor_name", "label": "Person's name", "sample": "Sam Rivera"},
    {"key": "status", "label": "Status", "sample": "In Progress"},
    {"key": "department", "label": "Department", "sample": "IT Support"},
    {"key": "department_suffix", "label": "for Department", "sample": " for IT Support"},
]

ANNOUNCEMENT_MERGE_FIELDS = [
    {"key": "brand_name", "label": "App name", "sample": "mlamehticket"},
    {"key": "announcement_title", "label": "Announcement title", "sample": "Office closed Friday"},
    {"key": "actor_name", "label": "Person's name", "sample": "Sam Rivera"},
]

DEFAULT_EMAIL_MESSAGES = {
    "new_ticket": {
        "subject": "[{{ brand_name }}] New ticket #{{ ticket_number }}: {{ ticket_title }}",
        "title": "New ticket #{{ ticket_number }}",
        "opening": "{{ actor_name }} submitted a new request{{ department_suffix }}.",
        "message_label": "Request",
        "button_label": "View ticket",
    },
    "ticket_picked": {
        "subject": "[{{ brand_name }}] Ticket #{{ ticket_number }} picked up",
        "title": "Ticket #{{ ticket_number }} was picked up",
        "opening": "{{ actor_name }} is now handling this ticket. Status is {{ status }}.",
        "message_label": "Request",
        "button_label": "Open ticket",
    },
    "ticket_message": {
        "subject": "[{{ brand_name }}] New reply on #{{ ticket_number }}",
        "title": "New reply on #{{ ticket_number }}",
        "opening": "{{ actor_name }} replied to the ticket.",
        "message_label": "Message",
        "button_label": "Open ticket",
    },
    "ticket_status": {
        "subject": "[{{ brand_name }}] Status update on #{{ ticket_number }}: {{ status }}",
        "title": "Status changed on #{{ ticket_number }}",
        "opening": "{{ actor_name }} updated the status to {{ status }}.",
        "message_label": "Request",
        "button_label": "Open ticket",
    },
    "ticket_update": {
        "subject": "[{{ brand_name }}] Update on ticket #{{ ticket_number }}",
        "title": "Ticket #{{ ticket_number }} was updated",
        "opening": "{{ actor_name }} made an update to this ticket.",
        "message_label": "Request",
        "button_label": "Open ticket",
    },
    "transfer_requested": {
        "subject": "[{{ brand_name }}] Transfer requested: #{{ ticket_number }}",
        "title": "Transfer requested for #{{ ticket_number }}",
        "opening": "{{ actor_name }} wants to transfer this ticket to you.",
        "message_label": "Request",
        "button_label": "Open ticket",
    },
    "transfer_accepted": {
        "subject": "[{{ brand_name }}] Transfer accepted: #{{ ticket_number }}",
        "title": "Transfer accepted for #{{ ticket_number }}",
        "opening": "{{ actor_name }} accepted the ticket transfer.",
        "message_label": "Request",
        "button_label": "Open ticket",
    },
    "transfer_denied": {
        "subject": "[{{ brand_name }}] Transfer declined: #{{ ticket_number }}",
        "title": "Transfer declined for #{{ ticket_number }}",
        "opening": "{{ actor_name }} declined the ticket transfer.",
        "message_label": "Request",
        "button_label": "Open ticket",
    },
    "announcement": {
        "subject": "[{{ brand_name }}] Announcement: {{ announcement_title }}",
        "title": "{{ announcement_title }}",
        "opening": "A new announcement has been posted in {{ brand_name }}.",
        "message_label": "Announcement",
        "button_label": "View announcements",
    },
}

_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_CHIP_RE = re.compile(
    r'<span[^>]*\bdata-merge-key=["\']([a-zA-Z0-9_]+)["\'][^>]*>.*?</span>',
    re.IGNORECASE | re.DOTALL,
)


def merge_fields_for_event(event_type: str) -> list[dict]:
    if event_type == "announcement":
        return list(ANNOUNCEMENT_MERGE_FIELDS)
    return list(TICKET_MERGE_FIELDS)


def event_meta(event_type: str) -> dict | None:
    for item in EVENT_META:
        if item["event_type"] == event_type:
            return item
    return None


def ensure_email_designer_defaults() -> None:
    from core.models import EmailBrand, EmailMessage

    EmailBrand.objects.get_or_create(
        pk=1,
        defaults={
            "brand_name": DEFAULT_BRAND_NAME,
            "accent_color": DEFAULT_ACCENT_COLOR,
            "footer_note": DEFAULT_FOOTER_NOTE,
            **BRAND_SURFACE_DEFAULTS,
        },
    )
    for event_type, fields in DEFAULT_EMAIL_MESSAGES.items():
        EmailMessage.objects.get_or_create(
            event_type=event_type,
            defaults={
                "subject": fields["subject"],
                "title": fields["title"],
                "opening": fields["opening"],
                "message_label": fields["message_label"],
                "button_label": fields["button_label"],
            },
        )


def get_email_brand():
    from core.models import EmailBrand

    ensure_email_designer_defaults()
    brand = EmailBrand.objects.first()
    if brand:
        return brand
    return EmailBrand(
        brand_name=DEFAULT_BRAND_NAME,
        accent_color=DEFAULT_ACCENT_COLOR,
        footer_note=DEFAULT_FOOTER_NOTE,
        **BRAND_SURFACE_DEFAULTS,
    )


def brand_surface_context(brand=None) -> dict:
    brand = brand or get_email_brand()
    layout = getattr(brand, "table_layout", None) or DEFAULT_TABLE_LAYOUT
    fill = getattr(brand, "table_fill_mode", None) or DEFAULT_TABLE_FILL_MODE
    radius = getattr(brand, "table_radius", None)
    pad_y = getattr(brand, "table_row_padding_y", None)
    pad_x = getattr(brand, "table_row_padding_x", None)
    label_w = getattr(brand, "table_label_width", None)
    if radius is None:
        radius = DEFAULT_TABLE_RADIUS
    if pad_y is None:
        pad_y = DEFAULT_TABLE_ROW_PADDING_Y
    if pad_x is None:
        pad_x = DEFAULT_TABLE_ROW_PADDING_X
    if label_w is None:
        label_w = DEFAULT_TABLE_LABEL_WIDTH
    # Pills use a large radius; clamp display radius for classic/compact/minimal.
    display_radius = 24 if layout == "pills" else min(int(radius), 24)
    return {
        "page_background": getattr(brand, "page_background", None) or DEFAULT_PAGE_BACKGROUND,
        "card_background": getattr(brand, "card_background", None) or DEFAULT_CARD_BACKGROUND,
        "table_header_bg": getattr(brand, "table_header_bg", None) or DEFAULT_TABLE_HEADER_BG,
        "table_border_color": getattr(brand, "table_border_color", None)
        or DEFAULT_TABLE_BORDER_COLOR,
        "text_color": getattr(brand, "text_color", None) or DEFAULT_TEXT_COLOR,
        "muted_text_color": getattr(brand, "muted_text_color", None) or DEFAULT_MUTED_TEXT_COLOR,
        "table_layout": layout,
        "table_fill_mode": fill,
        "table_radius": display_radius,
        "table_row_padding_y": int(pad_y),
        "table_row_padding_x": int(pad_x),
        "table_label_width": int(label_w),
        "table_show_outer_border": bool(
            getattr(brand, "table_show_outer_border", True)
        ),
        "table_show_row_dividers": bool(
            getattr(brand, "table_show_row_dividers", True)
        ),
        "table_font_size": 12 if layout == "compact" else 13,
        "table_pill_radius": "999px" if layout == "pills" else f"{display_radius}px",
    }


def get_email_message(event_type: str):
    from core.models import EmailMessage

    ensure_email_designer_defaults()
    return EmailMessage.objects.filter(event_type=event_type).first()


def render_token_string(template_str: str, context: dict, fallback: str = "") -> str:
    if not template_str or not str(template_str).strip():
        return fallback
    if "{%" in template_str or "%}" in template_str:
        logger.warning("Template tags are not allowed in email copy; using fallback")
        return fallback
    try:
        template = _TEMPLATE_ENGINE.from_string(template_str)
        rendered = template.render(Context(context or {}))
        return rendered if rendered.strip() else fallback
    except Exception as exc:
        logger.warning(
            "Invalid email token string; using fallback. template=%r error=%s",
            template_str,
            exc,
        )
        return fallback


def resolve_message_copy(event_type: str, context: dict, defaults: dict) -> dict:
    brand = get_email_brand()
    merged = {
        **(context or {}),
        "brand_name": brand.brand_name or DEFAULT_BRAND_NAME,
    }
    message = get_email_message(event_type)

    def field(name: str, default_key: str | None = None) -> str:
        key = default_key or name
        raw = getattr(message, name, "") if message else ""
        return render_token_string(raw, merged, fallback=defaults.get(key, ""))

    return {
        "subject": field("subject"),
        "title": field("title", "title"),
        "headline": field("title", "title"),
        "opening": field("opening", "opening"),
        "intro": field("opening", "opening"),
        "message_label": field("message_label", "message_label"),
        "message_title": field("message_label", "message_label"),
        "button_label": field("button_label", "button_label"),
        "cta_label": field("button_label", "button_label"),
        "brand_name": brand.brand_name or DEFAULT_BRAND_NAME,
        "accent_color": brand.accent_color or DEFAULT_ACCENT_COLOR,
        "footer_note": brand.footer_note or DEFAULT_FOOTER_NOTE,
        **brand_surface_context(brand),
    }


def tokens_to_chips_html(value: str, event_type: str) -> str:
    """Convert {{ key }} tokens into non-editable chip spans for contenteditable."""
    fields = {f["key"]: f["label"] for f in merge_fields_for_event(event_type)}

    def repl(match: re.Match) -> str:
        key = match.group(1)
        label = fields.get(key, key.replace("_", " ").title())
        return (
            f'<span class="email-merge-chip" data-merge-key="{escape(key)}" '
            f'contenteditable="false">{escape(label)}</span>'
        )

    text = value or ""
    # Escape plain text segments while preserving token replacements.
    parts = []
    last = 0
    for match in _TOKEN_RE.finditer(text):
        parts.append(escape(text[last:match.start()]))
        parts.append(repl(match))
        last = match.end()
    parts.append(escape(text[last:]))
    # Preserve line breaks for opening text.
    return "".join(parts).replace("\n", "<br>")


def chips_html_to_tokens(html: str) -> str:
    """Serialize contenteditable HTML (with chips) back to token strings."""
    if not html:
        return ""
    text = html
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>\s*<div[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>\s*<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<div[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)

    def chip_repl(match: re.Match) -> str:
        return "{{ " + match.group(1) + " }}"

    text = _CHIP_RE.sub(chip_repl, text)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).replace("\xa0", " ").strip()


def sample_context_for_event(event_type: str, brand_name: str | None = None) -> dict:
    fields = merge_fields_for_event(event_type)
    ctx = {f["key"]: f["sample"] for f in fields}
    if brand_name:
        ctx["brand_name"] = brand_name
    return ctx
