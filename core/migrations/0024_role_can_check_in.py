from django.db import migrations, models


def grant_check_in(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    User = apps.get_model("accounts", "User")
    support_role_ids = list(
        User.objects.filter(user_type="support", role_id__isnull=False).values_list("role_id", flat=True)
    )
    if support_role_ids:
        Role.objects.filter(pk__in=support_role_ids).update(can_check_in=True)
    for role in Role.objects.all():
        if role.name and role.name.strip().lower() == "admin":
            role.can_check_in = True
            role.save(update_fields=["can_check_in"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_role_can_manage_shifts"),
        ("accounts", "0008_alter_requires_password_change_verbose"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_check_in",
            field=models.BooleanField(default=False, verbose_name="Check in to shifts"),
        ),
        migrations.RunPython(grant_check_in, noop),
    ]
