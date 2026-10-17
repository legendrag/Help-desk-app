from django.db import migrations

OLD_LINE = "Check-in is open now."
NEW_LINE = "{{ check_in_note }}"


def use_check_in_note(apps, schema_editor):
    # Saved reminder templates told every role to check in. Swap the fixed
    # line for the field that follows the role; edited wording is left alone.
    EmailTemplate = apps.get_model("core", "EmailTemplate")
    for row in EmailTemplate.objects.filter(event_type="shift_reminder", body__contains=OLD_LINE):
        row.body = row.body.replace(OLD_LINE, NEW_LINE)
        row.save(update_fields=["body"])


def restore_fixed_line(apps, schema_editor):
    EmailTemplate = apps.get_model("core", "EmailTemplate")
    for row in EmailTemplate.objects.filter(event_type="shift_reminder", body__contains=NEW_LINE):
        row.body = row.body.replace(NEW_LINE, OLD_LINE)
        row.save(update_fields=["body"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_shift_reminder_email"),
    ]

    operations = [
        migrations.RunPython(use_check_in_note, restore_fixed_line),
    ]
