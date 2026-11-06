# Generated for PDF Master initial release.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="ProcessedFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tool", models.CharField(max_length=40)),
                ("original_name", models.CharField(blank=True, max_length=255)),
                ("output_file", models.FileField(upload_to="processed/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
