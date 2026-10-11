from datetime import time

from django.db import migrations, models
import django.db.models.deletion


def seed_night_cutoff(apps, schema_editor):
    Department = apps.get_model("core", "Department")
    Settings = apps.get_model("shifts", "DepartmentShiftSettings")
    ShiftType = apps.get_model("shifts", "ShiftType")
    from shifts.services import type_includes_night

    cutoff = time(18, 0)
    for department in Department.objects.all():
        Settings.objects.get_or_create(
            department=department,
            defaults={"night_starts_at": cutoff},
        )
        for row in ShiftType.objects.filter(department=department):
            night = type_includes_night(row.start_time, row.end_time, cutoff)
            if row.is_night != night:
                row.is_night = night
                row.save(update_fields=["is_night"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0024_role_can_check_in"),
        ("shifts", "0003_shiftassignment_checked_out_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepartmentShiftSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("night_starts_at", models.TimeField(default=time(18, 0), verbose_name="Night starts at")),
                (
                    "department",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shift_settings",
                        to="core.department",
                        verbose_name="Department",
                    ),
                ),
            ],
            options={
                "verbose_name": "Shift settings",
                "verbose_name_plural": "Shift settings",
            },
        ),
        migrations.RemoveConstraint(
            model_name="shiftassignment",
            name="uniq_shift_assignment_user_date",
        ),
        migrations.AddConstraint(
            model_name="shiftassignment",
            constraint=models.UniqueConstraint(
                fields=("user", "date", "shift_type"),
                name="uniq_shift_assignment_user_date_type",
            ),
        ),
        migrations.RunPython(seed_night_cutoff, migrations.RunPython.noop),
    ]
