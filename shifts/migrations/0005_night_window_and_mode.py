from datetime import time

from django.db import migrations, models


def recompute_night_flags(apps, schema_editor):
    """Night now runs from the night start to the night end (default 6 AM), and a
    type is a night shift when more than half its hours are night hours."""
    ShiftType = apps.get_model("shifts", "ShiftType")
    Settings = apps.get_model("shifts", "DepartmentShiftSettings")
    from shifts.services import is_night_shift

    windows = {
        row.department_id: (row.night_starts_at, row.night_ends_at)
        for row in Settings.objects.all()
    }
    for row in ShiftType.objects.all():
        starts, ends = windows.get(row.department_id, (time(18, 0), time(6, 0)))
        night = is_night_shift(row.start_time, row.end_time, starts, ends, mode=row.night_mode)
        if row.is_night != night:
            row.is_night = night
            row.save(update_fields=["is_night"])


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0004_same_day_shifts"),
    ]

    operations = [
        migrations.AddField(
            model_name="departmentshiftsettings",
            name="night_ends_at",
            field=models.TimeField(default=time(6, 0), verbose_name="Night ends at"),
        ),
        migrations.AddField(
            model_name="shifttype",
            name="night_mode",
            field=models.CharField(
                choices=[("auto", "Automatic"), ("always", "Always"), ("never", "Never")],
                default="auto",
                max_length=10,
                verbose_name="Counts as night shift",
            ),
        ),
        migrations.RunPython(recompute_night_flags, migrations.RunPython.noop),
    ]
