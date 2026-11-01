import logging
from datetime import timedelta

from django.utils import timezone
from plotly.graph_objs import Scatter
from plotly.offline import plot

from dashboard.models import SharePriceHistory

logger = logging.getLogger("main")


def build_plot(x_data, y_data, name="Цена"):
    if not x_data or not y_data:
        return ""
    return plot(
        [
            Scatter(
                x=x_data,
                y=y_data,
                mode="lines",
                name=name,
                opacity=0.8,
                marker_color="red",
            )
        ],
        output_type="div",
        show_link=False,
        link_text="",
        include_plotlyjs=False,
    )


def get_graph_from_history(share, days=180):
    since = timezone.now() - timedelta(days=days)
    history = SharePriceHistory.objects.filter(
        share=share, recorded_at__gte=since
    ).order_by("recorded_at")
    x_data = [point.recorded_at for point in history]
    y_data = [float(point.price) for point in history]
    return build_plot(x_data, y_data, name=share.ticker)


def get_graph_from_tinkoff(share, days=180):
    from tinkoff.invest import CandleInterval, Client
    from tinkoff.invest.utils import now

    from config.settings import TINKOFF_TOKEN
    from dashboard.services.quotations import quotation_to_float

    if not TINKOFF_TOKEN:
        return ""

    with Client(TINKOFF_TOKEN) as client:
        x_data, y_data = [], []
        for candle in client.get_all_candles(
            figi=share.figi,
            from_=now() - timedelta(days=days),
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        ):
            x_data.append(candle.time.date())
            y_data.append(quotation_to_float(candle.close))
    return build_plot(x_data, y_data, name=share.ticker)


def get_graph(share, days=180):
    plot_div = get_graph_from_history(share, days=days)
    if plot_div:
        return plot_div
    try:
        return get_graph_from_tinkoff(share, days=days)
    except ImportError:
        logger.info("Tinkoff SDK is not installed; chart uses stored history only")
        return ""
    except Exception as exc:
        logger.error("Failed to build Tinkoff chart for share %s: %s", share.id, exc)
        return ""
