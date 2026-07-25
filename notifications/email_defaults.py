"""Built-in default copy for notification emails (fallback + migration seed)."""

DEFAULT_BRAND_NAME = "mlamehticket"
DEFAULT_ACCENT_COLOR = "#4f46e5"
DEFAULT_FOOTER_NOTE = (
    "You’re receiving this because email notifications are enabled "
    "for your mlamehticket account."
)

# Placeholder templates seeded into EmailTemplate and used when DB copy is empty.
DEFAULT_EMAIL_TEMPLATES = {
    "new_ticket": {
        "subject": "[{{ brand_name }}] New ticket #{{ ticket_number }}: {{ ticket_title }}",
        "headline": "New ticket #{{ ticket_number }}",
        "intro": "{{ actor_name }} submitted a new request{{ department_suffix }}.",
        "message_title": "Request",
        "cta_label": "View ticket",
    },
    "ticket_picked": {
        "subject": "[{{ brand_name }}] Ticket #{{ ticket_number }} picked up",
        "headline": "Ticket #{{ ticket_number }} was picked up",
        "intro": "{{ actor_name }} is now handling this ticket. Status is {{ status }}.",
        "message_title": "Request",
        "cta_label": "Open ticket",
    },
    "ticket_message": {
        "subject": "[{{ brand_name }}] New reply on #{{ ticket_number }}",
        "headline": "New reply on #{{ ticket_number }}",
        "intro": "{{ actor_name }} replied to the ticket.",
        "message_title": "Message",
        "cta_label": "Open ticket",
    },
    "ticket_status": {
        "subject": "[{{ brand_name }}] Status update on #{{ ticket_number }}: {{ status }}",
        "headline": "Status changed on #{{ ticket_number }}",
        "intro": "{{ actor_name }} updated the status to {{ status }}.",
        "message_title": "Request",
        "cta_label": "Open ticket",
    },
    "ticket_update": {
        "subject": "[{{ brand_name }}] Update on ticket #{{ ticket_number }}",
        "headline": "Ticket #{{ ticket_number }} was updated",
        "intro": "{{ actor_name }} made an update to this ticket.",
        "message_title": "Request",
        "cta_label": "Open ticket",
    },
    "transfer_requested": {
        "subject": "[{{ brand_name }}] Transfer requested: #{{ ticket_number }}",
        "headline": "Transfer requested for #{{ ticket_number }}",
        "intro": "{{ actor_name }} wants to transfer this ticket to you.",
        "message_title": "Request",
        "cta_label": "Open ticket",
    },
    "transfer_accepted": {
        "subject": "[{{ brand_name }}] Transfer accepted: #{{ ticket_number }}",
        "headline": "Transfer accepted for #{{ ticket_number }}",
        "intro": "{{ actor_name }} accepted the ticket transfer.",
        "message_title": "Request",
        "cta_label": "Open ticket",
    },
    "transfer_denied": {
        "subject": "[{{ brand_name }}] Transfer declined: #{{ ticket_number }}",
        "headline": "Transfer declined for #{{ ticket_number }}",
        "intro": "{{ actor_name }} declined the ticket transfer.",
        "message_title": "Request",
        "cta_label": "Open ticket",
    },
    "announcement": {
        "subject": "[{{ brand_name }}] Announcement: {{ announcement_title }}",
        "headline": "{{ announcement_title }}",
        "intro": "A new announcement has been posted in {{ brand_name }}.",
        "message_title": "Announcement",
        "cta_label": "View announcements",
    },
}

# Friendly insert chips for the Settings editor (label shown to users).
TICKET_INSERT_FIELDS = [
    {"key": "brand_name", "label": "App name", "sample": "mlamehticket"},
    {"key": "ticket_number", "label": "Ticket number", "sample": "TK-1042"},
    {"key": "ticket_title", "label": "Ticket title", "sample": "Printer offline"},
    {"key": "actor_name", "label": "Person's name", "sample": "Sam Rivera"},
    {"key": "status", "label": "Status", "sample": "In Progress"},
    {"key": "department", "label": "Department", "sample": "IT Support"},
    {"key": "department_suffix", "label": "for Department", "sample": " for IT Support"},
]

ANNOUNCEMENT_INSERT_FIELDS = [
    {"key": "brand_name", "label": "App name", "sample": "mlamehticket"},
    {"key": "announcement_title", "label": "Announcement title", "sample": "Office closed Friday"},
    {"key": "actor_name", "label": "Person's name", "sample": "Sam Rivera"},
]

# Kept for any older imports / docs.
TICKET_PLACEHOLDERS = [f"{{{{ {f['key']} }}}}" for f in TICKET_INSERT_FIELDS]
ANNOUNCEMENT_PLACEHOLDERS = [f"{{{{ {f['key']} }}}}" for f in ANNOUNCEMENT_INSERT_FIELDS]


def ensure_email_format_defaults():
    """Create appearance + templates if missing (safe for tests and fresh DBs)."""
    from core.models import EmailAppearance, EmailTemplate

    EmailAppearance.objects.get_or_create(
        pk=1,
        defaults={
            "brand_name": DEFAULT_BRAND_NAME,
            "accent_color": DEFAULT_ACCENT_COLOR,
            "footer_note": DEFAULT_FOOTER_NOTE,
        },
    )
    for event_type, fields in DEFAULT_EMAIL_TEMPLATES.items():
        EmailTemplate.objects.get_or_create(
            event_type=event_type,
            defaults={
                "subject": fields["subject"],
                "headline": fields["headline"],
                "intro": fields["intro"],
                "message_title": fields["message_title"],
                "cta_label": fields["cta_label"],
                "is_active": True,
            },
        )
