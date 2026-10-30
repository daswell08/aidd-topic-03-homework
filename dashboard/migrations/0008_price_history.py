from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0007_add_updated_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("price", models.DecimalField(decimal_places=9, max_digits=20)),
                ("recorded_at", models.DateTimeField()),
                (
                    "share",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_history",
                        to="dashboard.share",
                    ),
                ),
            ],
            options={
                "verbose_name": "История цены",
                "verbose_name_plural": "История цен",
                "ordering": ["recorded_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("share", "recorded_at"),
                        name="unique_share_price_timestamp",
                    )
                ],
            },
        ),
    ]
