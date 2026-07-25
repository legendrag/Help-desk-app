from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_emailbrand_table_layout"),
    ]

    operations = [
        migrations.DeleteModel(name="EmailMessage"),
        migrations.DeleteModel(name="EmailBrand"),
    ]
