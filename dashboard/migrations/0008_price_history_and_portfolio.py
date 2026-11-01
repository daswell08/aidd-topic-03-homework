import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dashboard", "0007_add_updated_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="share",
            name="ticker",
            field=models.CharField(max_length=32, unique=True, verbose_name="Тикер"),
        ),
        migrations.CreateModel(
            name="SharePriceHistory",
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
                ("price", models.DecimalField(decimal_places=6, max_digits=18)),
                ("recorded_at", models.DateTimeField(db_index=True)),
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
            },
        ),
        migrations.CreateModel(
            name="PortfolioPosition",
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
                ("quantity", models.PositiveIntegerField(default=0)),
                (
                    "average_price",
                    models.DecimalField(decimal_places=6, default=0, max_digits=18),
                ),
                (
                    "share",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portfolio_positions",
                        to="dashboard.share",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portfolio_positions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Позиция портфеля",
                "verbose_name_plural": "Позиции портфеля",
                "unique_together": {("user", "share")},
            },
        ),
        migrations.CreateModel(
            name="PortfolioTransaction",
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
                (
                    "side",
                    models.CharField(
                        choices=[("buy", "Покупка"), ("sell", "Продажа")],
                        max_length=4,
                    ),
                ),
                ("quantity", models.PositiveIntegerField()),
                ("price", models.DecimalField(decimal_places=6, max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "share",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="portfolio_transactions",
                        to="dashboard.share",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portfolio_transactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Операция портфеля",
                "verbose_name_plural": "Операции портфеля",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="sharepricehistory",
            index=models.Index(
                fields=["share", "recorded_at"],
                name="dashboard_s_share_i_7c9f1a_idx",
            ),
        ),
    ]
