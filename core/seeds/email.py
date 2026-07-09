from core.models import EmailSetting
from core.seeds import data


def seed_email(stdout=None):
    setting, created = EmailSetting.objects.get_or_create(
        smtp_host=data.DEMO_EMAIL_HOST,
        defaults={
            "smtp_port": 587,
            "smtp_email": "noreply@deskplus.local",
            "smtp_password": "demo-not-for-production",
            "encryption": "tls",
            "from_name": "DeskPlus Demo",
            "from_email": "noreply@deskplus.local",
            "is_active": False,
            "notify_new_ticket": True,
            "notify_ticket_picked": True,
            "notify_ticket_message": True,
            "notify_ticket_status": True,
            "notify_ticket_update": True,
        },
    )
    if not created:
        setting.is_active = False
        setting.save(update_fields=["is_active"])

    if stdout:
        label = "created" if created else "updated"
        stdout.write(f"  Demo email setting ({label}, inactive)")

    return setting
