from django.db import migrations


def normalize_email_null(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(email="").update(email=None)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_alter_user_user_type"),
    ]

    operations = [
        migrations.RunPython(normalize_email_null, migrations.RunPython.noop),
    ]
