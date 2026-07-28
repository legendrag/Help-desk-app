"""Stop using title_ar/message_ar model fields.

Arabic copy is stored in the existing params JSON field so notification
creation works even when migration 0007 was never applied. Orphan DB
columns (if 0007 ran) are left in place intentionally.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_inappnotification_title_ar_message_ar"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="inappnotification",
                    name="title_ar",
                ),
                migrations.RemoveField(
                    model_name="inappnotification",
                    name="message_ar",
                ),
            ],
            database_operations=[],
        ),
    ]
