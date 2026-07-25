from core.models import EmailAppearance, EmailSetting, EmailTemplate
from core.seeds import data
from notifications.email_defaults import (
    DEFAULT_ACCENT_COLOR,
    DEFAULT_BRAND_NAME,
    DEFAULT_EMAIL_TEMPLATES,
    DEFAULT_FOOTER_NOTE,
)


def seed_email(stdout=None):
    setting, created = EmailSetting.objects.get_or_create(
        smtp_host=data.DEMO_EMAIL_HOST,
        defaults={
            "smtp_port": 587,
            "smtp_email": "noreply@mlamehticket.local",
            "smtp_password": "demo-not-for-production",
            "encryption": "tls",
            "from_name": "mlamehticket Demo",
            "from_email": "noreply@mlamehticket.local",
            "is_active": False,
            "notify_new_ticket": True,
            "notify_ticket_picked": True,
            "notify_ticket_message": True,
            "notify_ticket_status": True,
            "notify_ticket_update": True,
            "notify_announcement": True,
        },
    )
    if not created:
        setting.is_active = False
        setting.save(update_fields=["is_active"])

    appearance, appearance_created = EmailAppearance.objects.get_or_create(
        pk=1,
        defaults={
            "brand_name": DEFAULT_BRAND_NAME,
            "accent_color": DEFAULT_ACCENT_COLOR,
            "footer_note": DEFAULT_FOOTER_NOTE,
        },
    )

    templates_created = 0
    for event_type, fields in DEFAULT_EMAIL_TEMPLATES.items():
        _, tmpl_created = EmailTemplate.objects.get_or_create(
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
        if tmpl_created:
            templates_created += 1

    if stdout:
        label = "created" if created else "updated"
        stdout.write(f"  Demo email setting ({label}, inactive)")
        appearance_label = "created" if appearance_created else "exists"
        stdout.write(f"  Email appearance ({appearance_label})")
        stdout.write(f"  Email templates ({templates_created} created)")

    return setting
