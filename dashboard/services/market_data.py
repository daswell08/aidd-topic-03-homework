import logging

from config.settings import TINKOFF_TOKEN
from dashboard.services.quotations import as_aware_datetime, quotation_to_float

logger = logging.getLogger("main")


def _client_class():
    try:
        from tinkoff.invest import Client
    except ImportError as exc:
        raise RuntimeError(
            "Package tinkoff-investments is not installed"
        ) from exc
    return Client


def get_last_data(share):
    if not TINKOFF_TOKEN:
        raise RuntimeError("TINKOFF_TOKEN is not configured")

    with _client_class()(TINKOFF_TOKEN) as client:
        resp = client.market_data.get_last_prices(figi=[share.figi])
        if not resp.last_prices:
            raise RuntimeError(f"No last price returned for {share.figi}")
        last = resp.last_prices[0]
        logger.info("Get last data for share with id %s", share.id)
        return quotation_to_float(last.price), as_aware_datetime(last.time)
