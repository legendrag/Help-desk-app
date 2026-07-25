from django.db import migrations, models


STYLE_TO_FILL = {
    "plain": "none",
    "striped": "striped",
    "filled": "labels",
}


def forwards_migrate_table_style(apps, schema_editor):
    EmailBrand = apps.get_model("core", "EmailBrand")
    for brand in EmailBrand.objects.all():
        old = getattr(brand, "table_style", None) or "striped"
        brand.table_fill_mode = STYLE_TO_FILL.get(old, "striped")
        brand.table_layout = "classic"
        brand.save(
            update_fields=[
                "table_fill_mode",
                "table_layout",
            ]
        )


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_emailbrand_surface_colors"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailbrand",
            name="table_layout",
            field=models.CharField(
                choices=[
                    ("classic", "Classic"),
                    ("compact", "Compact"),
                    ("minimal", "Minimal"),
                    ("pills", "Pills"),
                ],
                default="classic",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_fill_mode",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("striped", "Striped"),
                    ("labels", "Labels"),
                ],
                default="striped",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_radius",
            field=models.PositiveSmallIntegerField(default=12),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_row_padding_y",
            field=models.PositiveSmallIntegerField(default=10),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_row_padding_x",
            field=models.PositiveSmallIntegerField(default=14),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_label_width",
            field=models.PositiveSmallIntegerField(default=38),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_show_outer_border",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_show_row_dividers",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(forwards_migrate_table_style, backwards_noop),
        migrations.RemoveField(
            model_name="emailbrand",
            name="table_style",
        ),
    ]
