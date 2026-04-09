from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0002_ticket_closed_at_ticket_last_status_change_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketmessage",
            name="reply_to",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="replies", to="tickets.ticketmessage"),
        ),
    ]
