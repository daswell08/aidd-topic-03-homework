from decimal import Decimal

from django.db import transaction

from dashboard.models import (
    InvestmentStrategy,
    PriceAlert,
    PriceAlertNotification,
    StrategyTrade,
)

ZERO = Decimal("0")


@transaction.atomic
def process_price_alerts(share, price, recorded_at):
    alerts = PriceAlert.objects.select_for_update().filter(share=share, is_active=True)
    for alert in alerts:
        is_triggered = (
            price >= alert.target_price
            if alert.direction == PriceAlert.Direction.ABOVE
            else price <= alert.target_price
        )
        if is_triggered and alert.is_armed:
            PriceAlertNotification.objects.get_or_create(
                alert=alert,
                recorded_at=recorded_at,
                defaults={"price": price},
            )
            alert.is_armed = False
            alert.save(update_fields=["is_armed"])
        elif not is_triggered and not alert.is_armed:
            alert.is_armed = True
            alert.save(update_fields=["is_armed"])


@transaction.atomic
def process_investment_strategies(share, price, recorded_at):
    strategies = InvestmentStrategy.objects.select_for_update().filter(
        share=share, is_active=True
    )
    for strategy in strategies:
        if strategy.position_quantity == ZERO and price <= strategy.buy_below:
            trade, created = StrategyTrade.objects.get_or_create(
                strategy=strategy,
                side=StrategyTrade.Side.BUY,
                recorded_at=recorded_at,
                defaults={
                    "quantity": strategy.quantity,
                    "price": price,
                    "realized_profit": ZERO,
                },
            )
            if created:
                strategy.position_quantity = trade.quantity
                strategy.average_entry_price = trade.price
                strategy.save(
                    update_fields=[
                        "position_quantity",
                        "average_entry_price",
                        "updated_at",
                    ]
                )
        elif strategy.position_quantity > ZERO and price >= strategy.sell_above:
            trade, created = StrategyTrade.objects.get_or_create(
                strategy=strategy,
                side=StrategyTrade.Side.SELL,
                recorded_at=recorded_at,
                defaults={
                    "quantity": strategy.position_quantity,
                    "price": price,
                    "realized_profit": (price - strategy.average_entry_price)
                    * strategy.position_quantity,
                },
            )
            if created:
                strategy.realized_profit += trade.realized_profit
                strategy.position_quantity = ZERO
                strategy.average_entry_price = ZERO
                strategy.save(
                    update_fields=[
                        "realized_profit",
                        "position_quantity",
                        "average_entry_price",
                        "updated_at",
                    ]
                )
