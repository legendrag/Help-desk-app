"""Re-drop webpush_subscriptioninfo.user_agent if it is still present.

Migration 0004 was idempotent but some installs kept the NOT NULL column
(check miss / column reintroduced), which breaks subscribe with:

  OperationalError: (1364, "Field 'user_agent' doesn't have a default value")

This migration uses a case-insensitive existence check and is safe to run when
the column is already gone.
"""

from django.db import migrations


def drop_user_agent_if_exists(apps, schema_editor):
    from notifications.webpush_schema import drop_subscriptioninfo_user_agent_if_exists

    drop_subscriptioninfo_user_agent_if_exists(connection=schema_editor.connection)


def noop_reverse(apps, schema_editor):
    # Do not re-add user_agent on migrate backwards — it breaks the patched ORM.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0009_restore_title_ar_message_ar_state"),
        ("webpush", "0002_auto_20190603_0005"),
    ]

    operations = [
        migrations.RunPython(drop_user_agent_if_exists, noop_reverse),
    ]
