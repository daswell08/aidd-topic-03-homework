from decimal import Decimal

from tinkoff.invest import Client

from config.settings import TINKOFF_TOKEN, logger


def get_last_data(share):
    with Client(TINKOFF_TOKEN) as client:
        resp = client.market_data.get_last_prices(figi=[share.figi])
        resp = resp.last_prices.pop()
        logger.info(f"Get last data for share with id {share.id}")
        price = Decimal(resp.price.units) + Decimal(resp.price.nano) / Decimal(
            1_000_000_000
        )
        return price, resp.time
