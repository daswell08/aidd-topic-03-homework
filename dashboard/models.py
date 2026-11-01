from django.conf import settings
from django.db import models


class Share(models.Model):
    """Акция"""

    figi = models.CharField(max_length=255, unique=True)
    isin = models.CharField(max_length=255)
    name = models.CharField(max_length=255, verbose_name="Наименование компании")
    ticker = models.CharField(max_length=32, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(max_length=255, unique=True)
    last_price = models.FloatField(blank=True, null=True, verbose_name="Текущая цена")
    is_trend_high = models.BooleanField(
        blank=True, null=True, verbose_name="Растет цена"
    )
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"

    def __str__(self):
        return f"{self.ticker} — {self.name}"


class SharePriceHistory(models.Model):
    """Сохранённая рыночная цена акции."""

    share = models.ForeignKey(
        Share, on_delete=models.CASCADE, related_name="price_history"
    )
    price = models.DecimalField(max_digits=18, decimal_places=6)
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "История цены"
        verbose_name_plural = "История цен"
        ordering = ["recorded_at"]
        indexes = [
            models.Index(fields=["share", "recorded_at"]),
        ]

    def __str__(self):
        return f"{self.share.ticker} {self.price} @ {self.recorded_at}"


class PortfolioPosition(models.Model):
    """Текущая позиция пользователя по акции."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolio_positions",
    )
    share = models.ForeignKey(
        Share, on_delete=models.CASCADE, related_name="portfolio_positions"
    )
    quantity = models.PositiveIntegerField(default=0)
    average_price = models.DecimalField(max_digits=18, decimal_places=6, default=0)

    class Meta:
        verbose_name = "Позиция портфеля"
        verbose_name_plural = "Позиции портфеля"
        unique_together = ("user", "share")

    def __str__(self):
        return f"{self.user} {self.share.ticker} x{self.quantity}"


class PortfolioTransaction(models.Model):
    """Операция покупки или продажи в виртуальном портфеле."""

    BUY = "buy"
    SELL = "sell"
    SIDE_CHOICES = (
        (BUY, "Покупка"),
        (SELL, "Продажа"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolio_transactions",
    )
    share = models.ForeignKey(
        Share, on_delete=models.PROTECT, related_name="portfolio_transactions"
    )
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=18, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Операция портфеля"
        verbose_name_plural = "Операции портфеля"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_side_display()} {self.share.ticker} x{self.quantity}"
