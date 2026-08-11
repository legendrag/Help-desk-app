"""Drop the rogue 'user_agent' column from webpush_subscriptioninfo.

The django-webpush model does not define a 'user_agent' field, but some
databases have one with a NOT NULL constraint. Dropping it (when present)
brings the schema back in sync with the ORM model.

Idempotent: if the column is already absent (fresh MySQL installs), this is a no-op.
"""

from django.db import migrations


def _column_exists(schema_editor, table, column):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "mysql":
            cursor.execute(
                """
                SELECT 1 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                LIMIT 1
                """,
                [table, column],
            )
            return cursor.fetchone() is not None
        if connection.vendor == "sqlite":
            cursor.execute("PRAGMA table_info(%s)" % connection.ops.quote_name(table))
            return any(row[1] == column for row in cursor.fetchall())
        # Generic fallback
        editor = connection.introspection
        desc = editor.get_table_description(cursor, table)
        return any(getattr(col, "name", col[0]) == column for col in desc)


def drop_user_agent_if_exists(apps, schema_editor):
    table = "webpush_subscriptioninfo"
    column = "user_agent"
    if not _column_exists(schema_editor, table, column):
        return
    qn = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE %s DROP COLUMN %s" % (qn(table), qn(column))
        )


def add_user_agent(apps, schema_editor):
    table = "webpush_subscriptioninfo"
    column = "user_agent"
    if _column_exists(schema_editor, table, column):
        return
    qn = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE %s ADD COLUMN %s varchar(500) NOT NULL DEFAULT ''"
            % (qn(table), qn(column))
        )


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_inappnotification_notification_type"),
        ("webpush", "0002_auto_20190603_0005"),
    ]

    operations = [
        migrations.RunPython(drop_user_agent_if_exists, add_user_agent),
    ]
