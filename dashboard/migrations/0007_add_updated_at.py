from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0006_add_verbose_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="share",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
