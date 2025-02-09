from typing import NamedTuple

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
        self.configure_widgets()
        self.configure_plots()

    def configure_widgets(self):
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

    def configure_plots(self):
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
