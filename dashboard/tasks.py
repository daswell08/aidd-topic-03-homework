from decimal import Decimal

from django.db import transaction

from config.celery import app
from config.settings import logger
from dashboard.models import PriceHistory, Share
from dashboard.services.market_automation import (
    process_investment_strategies,
    process_price_alerts,
)
from dashboard.services.market_data import get_last_data


@app.task
def update_last_price():
    shares = Share.objects.all()

    for share in shares:
        try:
            last_price, recorded_at = get_last_data(share)

            is_trend_high = (
                share.last_price is None or Decimal(str(share.last_price)) <= last_price
            )

            with transaction.atomic():
                PriceHistory.objects.get_or_create(
                    share=share,
                    recorded_at=recorded_at,
                    defaults={"price": last_price},
                )
                share.last_price = last_price
                share.is_trend_high = is_trend_high
                share.save(update_fields=["last_price", "is_trend_high", "updated_at"])
            process_price_alerts(share, last_price, recorded_at)
            process_investment_strategies(share, last_price, recorded_at)
        except Exception:
            logger.exception(
                "Failed to update price and automation for share %s", share.pk
            )
