from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailsetting",
            name="notify_new_ticket",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailsetting",
            name="notify_ticket_picked",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailsetting",
            name="notify_ticket_message",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailsetting",
            name="notify_ticket_status",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailsetting",
            name="notify_ticket_update",
            field=models.BooleanField(default=True),
        ),
    ]
