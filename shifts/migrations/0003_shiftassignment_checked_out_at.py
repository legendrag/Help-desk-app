from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0002_shift_type_colour_validator"),
    ]

    operations = [
        migrations.AddField(
            model_name="shiftassignment",
            name="checked_out_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Checked out at"),
        ),
    ]
