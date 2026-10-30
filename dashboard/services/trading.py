from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from dashboard.models import Portfolio, PortfolioTransaction, Share

ZERO = Decimal("0")


def get_portfolio_positions(portfolio):
    positions = defaultdict(
        lambda: {
            "quantity": ZERO,
            "cost_basis": ZERO,
            "realized_profit": ZERO,
        }
    )

    transactions = portfolio.transactions.select_related("share").order_by(
        "created_at", "pk"
    )
    for item in transactions:
        position = positions[item.share_id]
        if item.side == PortfolioTransaction.Side.BUY:
            position["quantity"] += item.quantity
            position["cost_basis"] += item.quantity * item.price
        elif item.side == PortfolioTransaction.Side.SELL:
            if position["quantity"] <= ZERO:
                raise ValidationError("Портфель содержит продажу без позиции.")
            average_cost = position["cost_basis"] / position["quantity"]
            if item.quantity > position["quantity"]:
                raise ValidationError("Продажа превышает доступную позицию.")
            sold_quantity = item.quantity
            position["realized_profit"] += (item.price - average_cost) * sold_quantity
            position["cost_basis"] -= average_cost * sold_quantity
            position["quantity"] -= sold_quantity
        else:
            raise ValidationError("Портфель содержит неизвестный тип операции.")

    shares = Share.objects.in_bulk(positions.keys())
    results = []
    for share_id, position in positions.items():
        share = shares[share_id]
        quantity = position["quantity"]
        average_cost = position["cost_basis"] / quantity if quantity > ZERO else ZERO
        current_price = share.last_price
        current_value = current_price * quantity if current_price is not None else None
        unrealized_profit = (
            (current_price - average_cost) * quantity
            if current_price is not None
            else None
        )
        results.append(
            {
                "share": share,
                "quantity": quantity,
                "average_cost": average_cost,
                "current_value": current_value,
                "realized_profit": position["realized_profit"],
                "unrealized_profit": unrealized_profit,
                "total_profit": (
                    position["realized_profit"] + unrealized_profit
                    if unrealized_profit is not None
                    else None
                ),
            }
        )
    return results


@transaction.atomic
def record_portfolio_transaction(portfolio, *, share, side, quantity, price):
    portfolio = Portfolio.objects.select_for_update().get(pk=portfolio.pk)
    if side not in PortfolioTransaction.Side.values:
        raise ValidationError("Неизвестный тип операции.")
    if quantity <= ZERO:
        raise ValidationError("Количество должно быть больше нуля.")
    if price <= ZERO:
        raise ValidationError("Цена должна быть больше нуля.")
    if side == PortfolioTransaction.Side.SELL:
        position = next(
            (
                item
                for item in get_portfolio_positions(portfolio)
                if item["share"].pk == share.pk
            ),
            None,
        )
        available = position["quantity"] if position else ZERO
        if quantity > available:
            raise ValidationError(
                f"Нельзя продать {quantity}: в портфеле доступно {available}."
            )
    return PortfolioTransaction.objects.create(
        portfolio=portfolio,
        share=share,
        side=side,
        quantity=quantity,
        price=price,
    )
