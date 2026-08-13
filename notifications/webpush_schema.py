"""Keep webpush_subscriptioninfo aligned with our patched ORM (no user_agent).

django-webpush's current model defines user_agent, but we strip that field at
runtime (see notifications.apps). Some DBs still have a NOT NULL user_agent
column with no default, which makes POST /webpush/save_information return 500.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

TABLE = "webpush_subscriptioninfo"
COLUMN = "user_agent"


def _column_exists(connection, table: str, column: str) -> bool:
    with connection.cursor() as cursor:
        if connection.vendor == "mysql":
            cursor.execute(
                """
                SELECT 1 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND LOWER(TABLE_NAME) = LOWER(%s)
                  AND LOWER(COLUMN_NAME) = LOWER(%s)
                LIMIT 1
                """,
                [table, column],
            )
            return cursor.fetchone() is not None
        if connection.vendor == "sqlite":
            cursor.execute("PRAGMA table_info(%s)" % connection.ops.quote_name(table))
            return any(row[1].lower() == column.lower() for row in cursor.fetchall())
        editor = connection.introspection
        try:
            desc = editor.get_table_description(cursor, table)
        except Exception:
            return False
        return any(str(getattr(col, "name", col[0])).lower() == column.lower() for col in desc)


def drop_subscriptioninfo_user_agent_if_exists(connection=None) -> bool:
    """Drop user_agent when present. Returns True if a drop ran."""
    from django.db import connection as default_connection

    connection = connection or default_connection
    if not _column_exists(connection, TABLE, COLUMN):
        return False

    qn = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE %s DROP COLUMN %s" % (qn(TABLE), qn(COLUMN)))
    logger.warning(
        "Dropped %s.%s so webpush subscribe matches the patched SubscriptionInfo model",
        TABLE,
        COLUMN,
    )
    return True


_schema_ensured = False


def ensure_subscriptioninfo_schema() -> None:
    """Drop leftover user_agent once per process (safe if already gone)."""
    global _schema_ensured
    if _schema_ensured:
        return
    try:
        drop_subscriptioninfo_user_agent_if_exists()
        _schema_ensured = True
    except Exception:
        # DB may not be ready yet during early startup; retry next call.
        logger.debug("webpush schema ensure deferred", exc_info=True)
