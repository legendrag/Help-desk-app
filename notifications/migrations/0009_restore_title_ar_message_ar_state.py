"""Restore title_ar/message_ar on the model state.

Migration 0008 removed them from state only, which made Django omit the
columns from INSERT while the NOT NULL DB columns from 0007 remained —
every notification create then failed with IntegrityError.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0008_remove_title_ar_message_ar_from_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="inappnotification",
                    name="title_ar",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="inappnotification",
                    name="message_ar",
                    field=models.TextField(blank=True, default=""),
                ),
            ],
            database_operations=[],
        ),
    ]
