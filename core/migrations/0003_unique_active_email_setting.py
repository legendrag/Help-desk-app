from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_emailsetting_notifications"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="emailsetting",
            constraint=models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="uniq_active_email_setting",
            ),
        ),
    ]
