from decimal import Decimal

from config.celery import app
from dashboard.models import Share, SharePriceHistory
from dashboard.services.market_data import get_last_data
from dashboard.services.quotations import as_aware_datetime

import logging

logger = logging.getLogger("main")


def _is_trend_high(previous_price, last_price):
    if previous_price is None:
        return True
    return last_price >= previous_price


@app.task
def update_last_price():
    shares = Share.objects.all()

    for share in shares:
        try:
            last_price, observed_at = get_last_data(share)
            is_trend_high = _is_trend_high(share.last_price, last_price)
            observed_at = as_aware_datetime(observed_at)

            Share.objects.filter(id=share.id).update(
                last_price=last_price, is_trend_high=is_trend_high
            )
            SharePriceHistory.objects.create(
                share=share,
                price=Decimal(str(last_price)),
                recorded_at=observed_at,
            )
        except Exception as exc:
            logger.error("Failed to update last price for share %s: %s", share.id, exc)
