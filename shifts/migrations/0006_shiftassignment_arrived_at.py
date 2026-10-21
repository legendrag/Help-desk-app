from django.db import migrations, models


def copy_running_check_ins(apps, schema_editor):
    """Shifts checked in right now still hold the press time; ended ones lost it."""
    ShiftAssignment = apps.get_model("shifts", "ShiftAssignment")
    ShiftAssignment.objects.filter(checked_in_at__isnull=False).update(arrived_at=models.F("checked_in_at"))


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0005_night_window_and_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="shiftassignment",
            name="arrived_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Arrived at"),
        ),
        migrations.RunPython(copy_running_check_ins, migrations.RunPython.noop),
    ]
