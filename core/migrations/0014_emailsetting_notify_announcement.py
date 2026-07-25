from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_delete_rolepermission"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailsetting",
            name="notify_new_ticket",
            field=models.BooleanField(default=True, verbose_name="New tickets"),
        ),
        migrations.AlterField(
            model_name="emailsetting",
            name="notify_ticket_picked",
            field=models.BooleanField(default=True, verbose_name="Ticket picked"),
        ),
        migrations.AlterField(
            model_name="emailsetting",
            name="notify_ticket_message",
            field=models.BooleanField(default=True, verbose_name="Ticket messages"),
        ),
        migrations.AlterField(
            model_name="emailsetting",
            name="notify_ticket_status",
            field=models.BooleanField(default=True, verbose_name="Status changes"),
        ),
        migrations.AlterField(
            model_name="emailsetting",
            name="notify_ticket_update",
            field=models.BooleanField(default=True, verbose_name="Ticket updates"),
        ),
        migrations.AddField(
            model_name="emailsetting",
            name="notify_announcement",
            field=models.BooleanField(default=True, verbose_name="Announcements"),
        ),
    ]
