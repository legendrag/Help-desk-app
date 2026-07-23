# Generated manually for RolePermission removal

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_role_can_manage_maintenance"),
    ]

    operations = [
        migrations.DeleteModel(
            name="RolePermission",
        ),
    ]
