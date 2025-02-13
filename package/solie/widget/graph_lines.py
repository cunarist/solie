import re
from asyncio import sleep
from datetime import datetime, timedelta
from typing import NamedTuple

import numpy as np
import pandas as pd
from pyqtgraph import (
    AxisItem,
    PlotDataItem,
    PlotItem,
    PlotWidget,
    mkBrush,
    mkPen,
)
from PySide6.QtGui import QFont

from solie.utility import (
    AggregateTrade,
    BookTicker,
    MarkPrice,
    PercentAxisItem,
    TimeAxisItem,
)


class LinePair(NamedTuple):
    line_a: PlotDataItem
    line_b: PlotDataItem


class GraphLines:
    def __init__(self):
        # Create widgets.
        self.price_widget = PlotWidget()
        self.volume_widget = PlotWidget()
        self.abstract_widget = PlotWidget()
        self.asset_widget = PlotWidget()

        # Create plots.
        price_plot = self.price_widget.plotItem
        volume_plot = self.volume_widget.plotItem
        abstract_plot = self.abstract_widget.plotItem
        asset_plot = self.asset_widget.plotItem
        if not isinstance(price_plot, PlotItem):
            raise ValueError("Plot item is invalid")
        if not isinstance(volume_plot, PlotItem):
            raise ValueError("Plot item is invalid")
        if not isinstance(abstract_plot, PlotItem):
            raise ValueError("Plot item is invalid")
        if not isinstance(asset_plot, PlotItem):
            raise ValueError("Plot item is invalid")
        self.price_plot = price_plot
        self.volume_plot = volume_plot
        self.abstract_plot = abstract_plot
        self.asset_plot = asset_plot

        # Insert lines in price plots.
        self.book_tickers = LinePair(
            price_plot.plot(
                pen=mkPen("#3F3F3F"),
                connect="finite",
                stepMode="right",
            ),
            price_plot.plot(
                pen=mkPen("#3F3F3F"),
                connect="finite",
                stepMode="right",
            ),
        )
        self.last_price = price_plot.plot(
            pen=mkPen("#5A8CC2"),
            connect="finite",
            stepMode="right",
        )
        self.mark_price = price_plot.plot(
            pen=mkPen("#3E628A"),
            connect="finite",
        )
        self.price_indicators = [price_plot.plot(connect="finite") for _ in range(20)]
        self.entry_price = price_plot.plot(
            pen=mkPen("#FFBB00"),
            connect="finite",
        )
        self.wobbles = LinePair(
            price_plot.plot(
                pen=mkPen("#888888"),
                connect="finite",
                stepMode="right",
            ),
            price_plot.plot(
                pen=mkPen("#888888"),
                connect="finite",
                stepMode="right",
            ),
        )
        self.price_rise = price_plot.plot(
            pen=mkPen("#70E161"),
            connect="finite",
        )
        self.price_fall = price_plot.plot(
            pen=mkPen("#FF304F"),
            connect="finite",
        )
        self.price_stay = price_plot.plot(
            pen=mkPen("#DDDDDD"),
            connect="finite",
        )
        self.sell = price_plot.plot(
            pen=mkPen(None),  # invisible line
            symbol="o",
            symbolBrush="#0055FF",
            symbolPen=mkPen("#BBBBBB"),
            symbolSize=8,
        )
        self.buy = price_plot.plot(
            pen=mkPen(None),  # invisible line
            symbol="o",
            symbolBrush="#FF3300",
            symbolPen=mkPen("#BBBBBB"),
            symbolSize=8,
        )

        # Insert lines in volume plots.
        self.volume = volume_plot.plot(
            pen=mkPen("#BBBBBB"),
            connect="all",
            stepMode="right",
            fillLevel=0,
            brush=mkBrush(255, 255, 255, 15),
        )
        self.last_volume = volume_plot.plot(
            pen=mkPen("#BBBBBB"),
            connect="finite",
        )
        self.volume_indicators = [volume_plot.plot(connect="finite") for _ in range(20)]

        # Insert lines in abstract plots.
        self.abstract_indicators = [
            abstract_plot.plot(connect="finite") for _ in range(20)
        ]

        # Insert lines in asset plots.
        self.asset_with_unrealized_profit = asset_plot.plot(
            pen=mkPen("#999999"),
            connect="finite",
        )
        self.asset = asset_plot.plot(
            pen=mkPen("#FF8700"),
            connect="finite",
            stepMode="right",
        )

        # Configure UX.
        self._configure_widgets()
        self._configure_plots()

    def _configure_widgets(self):
        self.price_widget.setBackground("#252525")
        self.volume_widget.setBackground("#252525")
        self.abstract_widget.setBackground("#252525")
        self.asset_widget.setBackground("#252525")

        self.price_widget.setMouseEnabled(y=False)
        self.volume_widget.setMouseEnabled(y=False)
        self.abstract_widget.setMouseEnabled(y=False)
        self.asset_widget.setMouseEnabled(y=False)

        self.price_widget.enableAutoRange(y=True)
        self.volume_widget.enableAutoRange(y=True)
        self.abstract_widget.enableAutoRange(y=True)
        self.asset_widget.enableAutoRange(y=True)

        self.volume_widget.setXLink(self.price_widget)
        self.abstract_widget.setXLink(self.volume_widget)
        self.asset_widget.setXLink(self.abstract_widget)

    def _configure_plots(self):
        self.price_plot.vb.setLimits(xMin=0, yMin=0)  # type:ignore
        self.volume_plot.vb.setLimits(xMin=0, yMin=0)  # type:ignore
        self.abstract_plot.vb.setLimits(xMin=0)  # type:ignore
        self.asset_plot.vb.setLimits(xMin=0, yMin=0)  # type:ignore

        self.price_plot.setDownsampling(auto=True, mode="subsample")
        self.price_plot.setClipToView(True)
        self.price_plot.setAutoVisible(y=True)  # type:ignore
        self.volume_plot.setDownsampling(auto=True, mode="subsample")
        self.volume_plot.setClipToView(True)
        self.volume_plot.setAutoVisible(y=True)  # type:ignore
        self.abstract_plot.setDownsampling(auto=True, mode="subsample")
        self.abstract_plot.setClipToView(True)
        self.abstract_plot.setAutoVisible(y=True)  # type:ignore
        self.asset_plot.setDownsampling(auto=True, mode="subsample")
        self.asset_plot.setClipToView(True)
        self.asset_plot.setAutoVisible(y=True)  # type:ignore

        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": PercentAxisItem(orientation="left"),
            "right": PercentAxisItem(orientation="right"),
        }
        self.price_plot.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": AxisItem(orientation="left"),
            "right": AxisItem(orientation="right"),
        }
        self.volume_plot.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": AxisItem(orientation="left"),
            "right": AxisItem(orientation="right"),
        }
        self.abstract_plot.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": PercentAxisItem(orientation="left"),
            "right": PercentAxisItem(orientation="right"),
        }
        self.asset_plot.setAxisItems(axis_items)

        tick_font = QFont("Source Code Pro", 7)
        self.price_plot.getAxis("top").setTickFont(tick_font)
        self.price_plot.getAxis("bottom").setTickFont(tick_font)
        self.price_plot.getAxis("left").setTickFont(tick_font)
        self.price_plot.getAxis("right").setTickFont(tick_font)
        self.volume_plot.getAxis("top").setTickFont(tick_font)
        self.volume_plot.getAxis("bottom").setTickFont(tick_font)
        self.volume_plot.getAxis("left").setTickFont(tick_font)
        self.volume_plot.getAxis("right").setTickFont(tick_font)
        self.abstract_plot.getAxis("top").setTickFont(tick_font)
        self.abstract_plot.getAxis("bottom").setTickFont(tick_font)
        self.abstract_plot.getAxis("left").setTickFont(tick_font)
        self.abstract_plot.getAxis("right").setTickFont(tick_font)
        self.asset_plot.getAxis("top").setTickFont(tick_font)
        self.asset_plot.getAxis("bottom").setTickFont(tick_font)
        self.asset_plot.getAxis("left").setTickFont(tick_font)
        self.asset_plot.getAxis("right").setTickFont(tick_font)

        self.price_plot.getAxis("left").setWidth(40)
        self.price_plot.getAxis("right").setWidth(40)
        self.volume_plot.getAxis("left").setWidth(40)
        self.volume_plot.getAxis("right").setWidth(40)
        self.abstract_plot.getAxis("left").setWidth(40)
        self.abstract_plot.getAxis("right").setWidth(40)
        self.asset_plot.getAxis("left").setWidth(40)
        self.asset_plot.getAxis("right").setWidth(40)

        self.price_plot.getAxis("bottom").setHeight(0)
        self.volume_plot.getAxis("top").setHeight(0)
        self.volume_plot.getAxis("bottom").setHeight(0)
        self.abstract_plot.getAxis("top").setHeight(0)
        self.abstract_plot.getAxis("bottom").setHeight(0)
        self.asset_plot.getAxis("top").setHeight(0)

        self.price_plot.showGrid(x=True, y=True, alpha=0.1)
        self.volume_plot.showGrid(x=True, y=True, alpha=0.1)
        self.abstract_plot.showGrid(x=True, y=True, alpha=0.1)
        self.asset_plot.showGrid(x=True, y=True, alpha=0.1)

    async def update_light_lines(
        self,
        mark_prices: list[MarkPrice],
        aggregate_trades: list[AggregateTrade],
        book_tickers: list[BookTicker],
        entry_price: float | None,
        observed_until: datetime,
    ):
        # mark price
        data_y = [d.mark_price for d in mark_prices]
        data_x = [d.timestamp / 10**3 for d in mark_prices]
        self.mark_price.setData(data_x, data_y)
        await sleep(0.0)

        # last price
        timestamps = [t.timestamp / 10**3 for t in aggregate_trades]

        data_x = timestamps.copy()
        data_y = [t.price for t in aggregate_trades]
        self.last_price.setData(data_x, data_y)
        await sleep(0.0)

        # last trade volume
        index_ar = np.array(timestamps)
        value_ar = np.array([t.volume for t in aggregate_trades])
        length = len(index_ar)
        zero_ar = np.zeros(length)
        nan_ar = np.empty(length)
        nan_ar[:] = np.nan
        data_x = np.repeat(index_ar, 3)
        data_y = np.stack([nan_ar, zero_ar, value_ar], axis=1).reshape(-1)
        self.last_volume.setData(data_x, data_y)
        await sleep(0.0)

        # book tickers
        data_x = [d.timestamp / 10**3 for d in book_tickers]
        data_y = [d.best_bid_price for d in book_tickers]
        self.book_tickers.line_a.setData(data_x, data_y)
        data_y = [d.best_ask_price for d in book_tickers]
        self.book_tickers.line_b.setData(data_x, data_y)
        await sleep(0.0)

        # entry price
        first_moment = observed_until - timedelta(hours=12)
        last_moment = observed_until + timedelta(hours=12)
        if entry_price is None:
            data_x = []
            data_y = []
        else:
            data_x = np.linspace(
                first_moment.timestamp(),
                last_moment.timestamp(),
                num=1000,
            )
            data_y = np.linspace(
                entry_price,
                entry_price,
                num=1000,
            )
        self.entry_price.setData(data_x, data_y)
        await sleep(0.0)

    async def update_heavy_lines(
        self,
        symbol: str,
        candle_data: pd.DataFrame,
        asset_record: pd.DataFrame,
        unrealized_changes: pd.Series,
    ):
        # price movement
        index_ar = candle_data.index.to_numpy(dtype=np.int64) / 10**9
        open_ar = candle_data[(symbol, "OPEN")].to_numpy()
        close_ar = candle_data[(symbol, "CLOSE")].to_numpy()
        high_ar = candle_data[(symbol, "HIGH")].to_numpy()
        low_ar = candle_data[(symbol, "LOW")].to_numpy()
        rise_ar = close_ar > open_ar
        fall_ar = close_ar < open_ar
        stay_ar = close_ar == open_ar
        length = len(index_ar)
        nan_ar = np.empty(length)
        nan_ar[:] = np.nan

        data_x = np.stack(
            [
                index_ar[rise_ar] + 2,
                index_ar[rise_ar] + 5,
                index_ar[rise_ar],
                index_ar[rise_ar] + 5,
                index_ar[rise_ar] + 8,
                index_ar[rise_ar],
                index_ar[rise_ar] + 5,
                index_ar[rise_ar] + 5,
                index_ar[rise_ar],
            ],
            axis=1,
        ).reshape(-1)
        data_y = np.stack(
            [
                open_ar[rise_ar],
                open_ar[rise_ar],
                nan_ar[rise_ar],
                close_ar[rise_ar],
                close_ar[rise_ar],
                nan_ar[rise_ar],
                high_ar[rise_ar],
                low_ar[rise_ar],
                nan_ar[rise_ar],
            ],
            axis=1,
        ).reshape(-1)
        self.price_rise.setData(data_x, data_y)
        await sleep(0.0)

        data_x = np.stack(
            [
                index_ar[fall_ar] + 2,
                index_ar[fall_ar] + 5,
                index_ar[fall_ar],
                index_ar[fall_ar] + 5,
                index_ar[fall_ar] + 8,
                index_ar[fall_ar],
                index_ar[fall_ar] + 5,
                index_ar[fall_ar] + 5,
                index_ar[fall_ar],
            ],
            axis=1,
        ).reshape(-1)
        data_y = np.stack(
            [
                open_ar[fall_ar],
                open_ar[fall_ar],
                nan_ar[fall_ar],
                close_ar[fall_ar],
                close_ar[fall_ar],
                nan_ar[fall_ar],
                high_ar[fall_ar],
                low_ar[fall_ar],
                nan_ar[fall_ar],
            ],
            axis=1,
        ).reshape(-1)
        self.price_fall.setData(data_x, data_y)
        await sleep(0.0)

        data_x = np.stack(
            [
                index_ar[stay_ar] + 2,
                index_ar[stay_ar] + 5,
                index_ar[stay_ar],
                index_ar[stay_ar] + 5,
                index_ar[stay_ar] + 8,
                index_ar[stay_ar],
                index_ar[stay_ar] + 5,
                index_ar[stay_ar] + 5,
                index_ar[stay_ar],
            ],
            axis=1,
        ).reshape(-1)
        data_y = np.stack(
            [
                open_ar[stay_ar],
                open_ar[stay_ar],
                nan_ar[stay_ar],
                close_ar[stay_ar],
                close_ar[stay_ar],
                nan_ar[stay_ar],
                high_ar[stay_ar],
                low_ar[stay_ar],
                nan_ar[stay_ar],
            ],
            axis=1,
        ).reshape(-1)
        self.price_stay.setData(data_x, data_y)
        await sleep(0.0)

        # wobbles
        sr = candle_data[(symbol, "HIGH")]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        self.wobbles.line_a.setData(data_x, data_y)
        await sleep(0.0)

        sr = candle_data[(symbol, "LOW")]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        self.wobbles.line_b.setData(data_x, data_y)
        await sleep(0.0)

        # trade volume
        sr = candle_data[(symbol, "VOLUME")]
        sr = sr.fillna(value=0)
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        self.volume.setData(data_x, data_y)
        await sleep(0.0)

        # asset
        data_x = asset_record["RESULT_ASSET"].index.to_numpy(dtype=np.int64) / 10**9
        data_y = asset_record["RESULT_ASSET"].to_numpy(dtype=np.float32)
        self.asset.setData(data_x, data_y)
        await sleep(0.0)

        # asset with unrealized profit
        sr = asset_record["RESULT_ASSET"]
        if len(sr) >= 2:
            sr = sr.resample("10S").ffill()
        unrealized_changes_sr = unrealized_changes.reindex(sr.index)
        sr = sr * (1 + unrealized_changes_sr)
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9 + 5
        data_y = sr.to_numpy(dtype=np.float32)
        self.asset_with_unrealized_profit.setData(data_x, data_y)
        await sleep(0.0)

        # buy and sell
        df = asset_record.loc[asset_record["SYMBOL"] == symbol]
        df = df[df["SIDE"] == "SELL"]
        sr = df["FILL_PRICE"]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        self.sell.setData(data_x, data_y)
        await sleep(0.0)

        df = asset_record.loc[asset_record["SYMBOL"] == symbol]
        df = df[df["SIDE"] == "BUY"]
        sr = df["FILL_PRICE"]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        self.buy.setData(data_x, data_y)
        await sleep(0.0)

    async def update_custom_lines(self, symbol: str, indicators: pd.DataFrame):
        columns = [str(n) for n in indicators.columns]

        # price indicators
        chosen_columns = [n for n in columns if n.startswith(f"{symbol}/PRICE")]
        df = indicators[chosen_columns]
        data_x = df.index.to_numpy(dtype=np.int64) / 10**9
        data_x += 5
        for turn, widget in enumerate(self.price_indicators):
            if turn < len(df.columns):
                column_name = str(df.columns[turn])
                sr = df[column_name]
                data_y = sr.to_numpy(dtype=np.float32)
                inside_strings = re.findall(r"\(([^)]+)", column_name)
                if len(inside_strings) == 0:
                    color = "#AAAAAA"
                else:
                    color = inside_strings[0]
                widget.setPen(color)
                widget.setData(data_x, data_y)
                await sleep(0.0)
            else:
                widget.clear()

        # trade volume indicators
        chosen_columns = [n for n in columns if n.startswith(f"{symbol}/VOLUME")]
        df = indicators[chosen_columns]
        data_x = df.index.to_numpy(dtype=np.int64) / 10**9
        data_x += 5
        for turn, widget in enumerate(self.volume_indicators):
            if turn < len(df.columns):
                column_name = str(df.columns[turn])
                sr = df[column_name]
                data_y = sr.to_numpy(dtype=np.float32)
                inside_strings = re.findall(r"\(([^)]+)", column_name)
                if len(inside_strings) == 0:
                    color = "#AAAAAA"
                else:
                    color = inside_strings[0]
                widget.setPen(color)
                widget.setData(data_x, data_y)
                await sleep(0.0)
            else:
                widget.clear()

        # abstract indicators
        chosen_columns = [n for n in columns if n.startswith(f"{symbol}/ABSTRACT")]
        df = indicators[chosen_columns]
        data_x = df.index.to_numpy(dtype=np.int64) / 10**9
        data_x += 5
        for turn, widget in enumerate(self.abstract_indicators):
            if turn < len(df.columns):
                column_name = str(df.columns[turn])
                sr = df[column_name]
                data_y = sr.to_numpy(dtype=np.float32)
                inside_strings = re.findall(r"\(([^)]+)", column_name)
                if len(inside_strings) == 0:
                    color = "#AAAAAA"
                else:
                    color = inside_strings[0]
                widget.setPen(color)
                widget.setData(data_x, data_y)
                await sleep(0.0)
            else:
                widget.clear()
