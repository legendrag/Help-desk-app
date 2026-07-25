# Generated manually for email surface / table styling

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_email_brand_and_messages"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailbrand",
            name="page_background",
            field=models.CharField(default="#f8fafc", max_length=7),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="card_background",
            field=models.CharField(default="#ffffff", max_length=7),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_header_bg",
            field=models.CharField(default="#f8fafc", max_length=7),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_border_color",
            field=models.CharField(default="#e2e8f0", max_length=7),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="text_color",
            field=models.CharField(default="#0f172a", max_length=7),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="muted_text_color",
            field=models.CharField(default="#64748b", max_length=7),
        ),
        migrations.AddField(
            model_name="emailbrand",
            name="table_style",
            field=models.CharField(
                choices=[
                    ("plain", "Plain"),
                    ("striped", "Striped rows"),
                    ("filled", "Filled labels"),
                ],
                default="striped",
                max_length=20,
            ),
        ),
    ]
