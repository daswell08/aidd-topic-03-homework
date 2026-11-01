from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from dashboard.models import PortfolioPosition, PortfolioTransaction, SharePriceHistory


def to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


@transaction.atomic
def execute_trade(user, share, side, quantity, price=None):
    quantity = int(quantity)
    if quantity <= 0:
        raise ValidationError("Количество должно быть положительным числом.")

    if price is None or price == "":
        price = share.last_price
    price = quantize_money(to_decimal(price))
    if price <= 0:
        raise ValidationError("Не удалось определить цену сделки.")

    if side not in {PortfolioTransaction.BUY, PortfolioTransaction.SELL}:
        raise ValidationError("Неизвестный тип операции.")

    position, _ = PortfolioPosition.objects.select_for_update().get_or_create(
        user=user,
        share=share,
        defaults={"quantity": 0, "average_price": Decimal("0")},
    )

    if side == PortfolioTransaction.BUY:
        old_qty = Decimal(position.quantity)
        new_qty = old_qty + Decimal(quantity)
        total_cost = old_qty * position.average_price + Decimal(quantity) * price
        position.quantity = int(new_qty)
        position.average_price = quantize_money(total_cost / new_qty)
    else:
        if quantity > position.quantity:
            raise ValidationError("Недостаточно акций в портфеле для продажи.")
        position.quantity -= quantity
        if position.quantity == 0:
            position.average_price = Decimal("0")

    position.save()

    return PortfolioTransaction.objects.create(
        user=user,
        share=share,
        side=side,
        quantity=quantity,
        price=price,
    )


def position_market_value(position) -> Decimal:
    last_price = to_decimal(position.share.last_price)
    return quantize_money(Decimal(position.quantity) * last_price)


def position_unrealized_pnl(position) -> Decimal:
    last_price = to_decimal(position.share.last_price)
    return quantize_money(
        (last_price - position.average_price) * Decimal(position.quantity)
    )


def summarize_portfolio(user):
    positions = (
        PortfolioPosition.objects.filter(user=user, quantity__gt=0)
        .select_related("share")
        .order_by("share__ticker")
    )
    rows = []
    total_value = Decimal("0")
    total_cost = Decimal("0")
    total_pnl = Decimal("0")
    for position in positions:
        market_value = position_market_value(position)
        cost = quantize_money(
            Decimal(position.quantity) * position.average_price
        )
        pnl = position_unrealized_pnl(position)
        rows.append(
            {
                "position": position,
                "market_value": market_value,
                "cost": cost,
                "pnl": pnl,
                "pnl_percent": (
                    quantize_money(pnl / cost * Decimal("100"))
                    if cost
                    else Decimal("0")
                ),
            }
        )
        total_value += market_value
        total_cost += cost
        total_pnl += pnl
    return {
        "rows": rows,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_pnl": total_pnl,
        "total_pnl_percent": (
            quantize_money(total_pnl / total_cost * Decimal("100"))
            if total_cost
            else Decimal("0")
        ),
    }


def price_history_stats(share, days=180):
    from datetime import timedelta

    since = timezone.now() - timedelta(days=days)
    points = list(
        SharePriceHistory.objects.filter(share=share, recorded_at__gte=since).order_by(
            "recorded_at"
        )
    )
    if not points:
        return {
            "points": [],
            "first": None,
            "last": None,
            "min_price": None,
            "max_price": None,
            "abs_change": None,
            "pct_change": None,
        }

    prices = [to_decimal(point.price) for point in points]
    first = prices[0]
    last = prices[-1]
    abs_change = quantize_money(last - first)
    pct_change = (
        quantize_money(abs_change / first * Decimal("100")) if first else Decimal("0")
    )
    return {
        "points": points,
        "first": first,
        "last": last,
        "min_price": min(prices),
        "max_price": max(prices),
        "abs_change": abs_change,
        "pct_change": pct_change,
    }
