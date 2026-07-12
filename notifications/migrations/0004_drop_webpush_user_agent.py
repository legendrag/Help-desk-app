"""Drop the rogue 'user_agent' column from webpush_subscriptioninfo.

The django-webpush v0.3.4 model does not define a 'user_agent' field, but the
production database has one with a NOT NULL constraint.  Every INSERT therefore
fails with an IntegrityError, which surfaces as a 500 on
POST /webpush/save_information.

Dropping the column brings the schema back in sync with the ORM model.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_inappnotification_notification_type"),
        ("webpush", "0002_auto_20190603_0005"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE webpush_subscriptioninfo DROP COLUMN user_agent;",
            reverse_sql=(
                "ALTER TABLE webpush_subscriptioninfo "
                "ADD COLUMN user_agent varchar(500) NOT NULL DEFAULT '';"
            ),
        ),
    ]
