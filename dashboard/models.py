from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Share(models.Model):
    """Акция"""

    figi = models.CharField(max_length=255, unique=True)
    isin = models.CharField(max_length=255)
    name = models.CharField(max_length=255, verbose_name="Наименование компании")
    ticker = models.CharField(max_length=10, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(max_length=255, unique=True)
    last_price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        blank=True,
        null=True,
        verbose_name="Текущая цена",
    )
    is_trend_high = models.BooleanField(
        blank=True, null=True, verbose_name="Растет цена"
    )
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"


class PriceHistory(models.Model):
    """A market price snapshot for a share."""

    share = models.ForeignKey(
        Share, on_delete=models.CASCADE, related_name="price_history"
    )
    price = models.DecimalField(max_digits=20, decimal_places=9)
    recorded_at = models.DateTimeField()

    class Meta:
        ordering = ["recorded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["share", "recorded_at"],
                name="unique_share_price_timestamp",
            )
        ]
        verbose_name = "История цены"
        verbose_name_plural = "История цен"


class WatchlistItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
    )
    share = models.ForeignKey(
        Share, on_delete=models.CASCADE, related_name="watchlist_items"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "share"], name="unique_user_watchlist_share"
            )
        ]
        ordering = ["share__name"]


class PriceAlert(models.Model):
    class Direction(models.TextChoices):
        ABOVE = "above", "Выше или равно"
        BELOW = "below", "Ниже или равно"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="price_alerts",
    )
    share = models.ForeignKey(
        Share, on_delete=models.CASCADE, related_name="price_alerts"
    )
    direction = models.CharField(max_length=5, choices=Direction.choices)
    target_price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
    )
    is_active = models.BooleanField(default=True)
    is_armed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["share__name", "target_price"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "share", "direction", "target_price"],
                name="unique_user_price_alert",
            )
        ]


class PriceAlertNotification(models.Model):
    alert = models.ForeignKey(
        PriceAlert, on_delete=models.CASCADE, related_name="notifications"
    )
    price = models.DecimalField(max_digits=20, decimal_places=9)
    recorded_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-recorded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["alert", "recorded_at"],
                name="unique_alert_trigger_timestamp",
            )
        ]


class Portfolio(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_user_portfolio_name"
            )
        ]


class PortfolioTransaction(models.Model):
    class Side(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="transactions"
    )
    share = models.ForeignKey(
        Share, on_delete=models.PROTECT, related_name="portfolio_transactions"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class InvestmentStrategy(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="investment_strategies",
    )
    share = models.ForeignKey(
        Share, on_delete=models.CASCADE, related_name="investment_strategies"
    )
    name = models.CharField(max_length=100)
    buy_below = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
    )
    sell_above = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
    )
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
    )
    position_quantity = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    average_entry_price = models.DecimalField(
        max_digits=20, decimal_places=9, default=0
    )
    realized_profit = models.DecimalField(max_digits=20, decimal_places=9, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(sell_above__gt=F("buy_below")),
                name="strategy_sell_above_buy",
            )
        ]


class StrategyTrade(models.Model):
    class Side(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    strategy = models.ForeignKey(
        InvestmentStrategy, on_delete=models.CASCADE, related_name="trades"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=9)
    realized_profit = models.DecimalField(max_digits=20, decimal_places=9, default=0)
    recorded_at = models.DateTimeField()

    class Meta:
        ordering = ["-recorded_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["strategy", "side", "recorded_at"],
                name="unique_strategy_trade_timestamp",
            )
        ]
