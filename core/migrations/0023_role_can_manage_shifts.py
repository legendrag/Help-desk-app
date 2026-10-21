from django.db import migrations, models


def grant_admin_roles(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    for role in Role.objects.all():
        if role.name and role.name.strip().lower() == "admin":
            role.can_manage_shifts = True
            role.save(update_fields=["can_manage_shifts"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_alter_i18n_verbose_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_manage_shifts",
            field=models.BooleanField(default=False, verbose_name="Manage Shifts"),
        ),
        migrations.RunPython(grant_admin_roles, noop),
    ]
