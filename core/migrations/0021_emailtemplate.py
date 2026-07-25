from django.db import migrations, models
import django.utils.timezone


DEFAULT_TEMPLATES = {
    "new_ticket": {
        "subject": "[{{ brand_name }}] New ticket #{{ ticket_number }}: {{ title }}",
        "body": (
            "New ticket #{{ ticket_number }}\n\n"
            "{{ requester }} submitted a new request for {{ department }}.\n\n"
            "{{ description }}"
        ),
    },
    "ticket_picked": {
        "subject": "[{{ brand_name }}] Ticket #{{ ticket_number }} picked up",
        "body": (
            "Ticket #{{ ticket_number }} was picked up\n\n"
            "{{ actor }} is now handling this ticket. Status is {{ status }}.\n\n"
            "{{ description }}"
        ),
    },
    "ticket_message": {
        "subject": "[{{ brand_name }}] New reply on #{{ ticket_number }}",
        "body": (
            "New reply on #{{ ticket_number }}\n\n"
            "{{ actor }} replied to the ticket.\n\n"
            "{{ message }}"
        ),
    },
    "ticket_status": {
        "subject": "[{{ brand_name }}] Status update on #{{ ticket_number }}: {{ status }}",
        "body": (
            "Status changed on #{{ ticket_number }}\n\n"
            "{{ actor }} updated the status to {{ status }}.\n\n"
            "{{ description }}"
        ),
    },
    "ticket_update": {
        "subject": "[{{ brand_name }}] Update on ticket #{{ ticket_number }}",
        "body": (
            "Ticket #{{ ticket_number }} was updated\n\n"
            "{{ actor }} made an update to this ticket.\n\n"
            "{{ description }}"
        ),
    },
    "transfer_requested": {
        "subject": "[{{ brand_name }}] Transfer requested: #{{ ticket_number }}",
        "body": (
            "Transfer requested for #{{ ticket_number }}\n\n"
            "{{ actor }} wants to transfer this ticket to you.\n\n"
            "{{ description }}"
        ),
    },
    "transfer_accepted": {
        "subject": "[{{ brand_name }}] Transfer accepted: #{{ ticket_number }}",
        "body": (
            "Transfer accepted for #{{ ticket_number }}\n\n"
            "{{ actor }} accepted the ticket transfer.\n\n"
            "{{ description }}"
        ),
    },
    "transfer_denied": {
        "subject": "[{{ brand_name }}] Transfer declined: #{{ ticket_number }}",
        "body": (
            "Transfer declined for #{{ ticket_number }}\n\n"
            "{{ actor }} declined the ticket transfer.\n\n"
            "{{ description }}"
        ),
    },
    "announcement": {
        "subject": "[{{ brand_name }}] Announcement: {{ title }}",
        "body": (
            "{{ title }}\n\n"
            "A new announcement has been posted in {{ brand_name }}.\n\n"
            "{{ content }}"
        ),
    },
}


def seed_email_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("core", "EmailTemplate")
    now = django.utils.timezone.now()
    for event_type, defaults in DEFAULT_TEMPLATES.items():
        EmailTemplate.objects.get_or_create(
            event_type=event_type,
            defaults={
                "subject": defaults["subject"],
                "body": defaults["body"],
                "created_at": now,
                "updated_at": now,
            },
        )


def unseed_email_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("core", "EmailTemplate")
    EmailTemplate.objects.filter(event_type__in=DEFAULT_TEMPLATES.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_remove_email_brand_and_messages"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("new_ticket", "New ticket"),
                            ("ticket_picked", "Ticket picked"),
                            ("ticket_message", "Ticket reply"),
                            ("ticket_status", "Status change"),
                            ("ticket_update", "Ticket update"),
                            ("transfer_requested", "Transfer requested"),
                            ("transfer_accepted", "Transfer accepted"),
                            ("transfer_denied", "Transfer declined"),
                            ("announcement", "Announcement"),
                        ],
                        max_length=40,
                        unique=True,
                    ),
                ),
                ("subject", models.CharField(max_length=255)),
                ("body", models.TextField()),
            ],
            options={
                "verbose_name": "Email template",
                "verbose_name_plural": "Email templates",
                "ordering": ["event_type"],
            },
        ),
        migrations.RunPython(seed_email_templates, unseed_email_templates),
    ]
