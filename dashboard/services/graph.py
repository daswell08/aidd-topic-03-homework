from datetime import timedelta

from plotly.graph_objs import Scatter
from plotly.offline import plot
from tinkoff.invest import CandleInterval, Client
from tinkoff.invest.utils import now

from config.settings import TINKOFF_TOKEN


def _render_graph(x_data, y_data, name):
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
    )


def get_history_graph(history):
    return _render_graph(
        [point.recorded_at for point in history],
        [float(point.price) for point in history],
        "Сохранённые цены",
    )


def get_graph(share, days=180):
    with Client(TINKOFF_TOKEN) as client:
        x_data, y_data = [], []
        for candle in client.get_all_candles(
            figi=share.figi,
            from_=now() - timedelta(days=days),
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        ):
            x_data.append(candle.time.date())
            y_data.append(
                candle.close.units + candle.close.nano / 1_000_000_000
            )
    return _render_graph(x_data, y_data, "Дневные цены")
