from django.core.management import call_command
from django.db import migrations, models


def create_cache_table(apps, schema_editor):
    # CACHES uses the database (shared by processes, kept across restarts).
    # createcachetable skips tables that already exist.
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0013_email_outbox'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailoutbox',
            name='sent_keys',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
