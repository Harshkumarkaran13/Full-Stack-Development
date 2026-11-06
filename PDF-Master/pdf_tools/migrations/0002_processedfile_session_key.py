from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pdf_tools", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="processedfile",
            name="session_key",
            field=models.CharField(blank=True, db_index=True, max_length=40),
        ),
    ]
