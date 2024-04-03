import asyncio
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Coroutine

import aiofiles
import aiofiles.os
import pandas as pd
import pyqtgraph
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6 import QtCore, QtGui, QtWidgets

from solie.common import PACKAGE_PATH, PACKAGE_VERSION
from solie.overlay import CoinSelection, DatapathInput, TokenSelection
from solie.utility import (
    ApiRequester,
    DataSettings,
    LogHandler,
    PercentAxisItem,
    TimeAxisItem,
    examine_data_files,
    internet_connected,
    is_internet_checked,
    monitor_internet,
    read_data_settings,
    read_datapath,
    save_data_settings,
    save_datapath,
)
from solie.widget import (
    AskPopup,
    BaseOverlay,
    BrandLabel,
    HorizontalDivider,
    SplashScreen,
    SymbolBox,
    ask,
    overlay,
)

from .compiled import Ui_MainWindow

logger = logging.getLogger(__name__)


class Window(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, app_close_event: asyncio.Event, scheduler: AsyncIOScheduler):
        super().__init__()

        self.app_close_event = app_close_event
        self.scheduler = scheduler

        self.datapath: Path
        self.data_settings: DataSettings

        self.price_labels: dict[str, QtWidgets.QLabel] = {}
        self.last_interaction = datetime.now(timezone.utc)

        self.plot_widget = pyqtgraph.PlotWidget()
        self.plot_widget_1 = pyqtgraph.PlotWidget()
        self.plot_widget_4 = pyqtgraph.PlotWidget()
        self.plot_widget_6 = pyqtgraph.PlotWidget()

        self.plot_widget_2 = pyqtgraph.PlotWidget()
        self.plot_widget_3 = pyqtgraph.PlotWidget()
        self.plot_widget_5 = pyqtgraph.PlotWidget()
        self.plot_widget_7 = pyqtgraph.PlotWidget()

        self.transaction_lines: dict[str, list[pyqtgraph.PlotDataItem]] = {}
        self.simulation_lines: dict[str, list[pyqtgraph.PlotDataItem]] = {}

        self.finalize_functions: list[Callable[..., Coroutine]] = []

        self.should_finalize = False
        self.should_confirm_closing = False
        self.last_interaction = datetime.now(timezone.utc)

    def closeEvent(self, event):  # noqa:N802
        event.ignore()

        async def job_close():
            if not self.should_finalize:
                self.app_close_event.set()

            if self.should_confirm_closing:
                answer = await ask(
                    "Really quit?",
                    "If Solie is not turned on, data collection gets stopped as well."
                    " Solie will proceed to finalizations such as closing network"
                    " connections and saving data.",
                    ["Cancel", "Shut down"],
                )

                if answer in (0, 1):
                    return

            AskPopup.done_event.set()
            BaseOverlay.done_event.set()

            self.gauge.hide()
            self.board.hide()
            self.closeEvent = lambda event: event.ignore()

            splash_screen = SplashScreen()
            self.centralWidget().layout().addWidget(splash_screen)

            self.scheduler.shutdown()
            await asyncio.sleep(1)

            await asyncio.wait(
                [asyncio.create_task(job()) for job in self.finalize_functions]
            )

            self.app_close_event.set()

        asyncio.create_task(job_close())

    def mouseReleaseEvent(self, event):  # noqa:N802
        self.last_interaction = datetime.now(timezone.utc)

        if self.board.isEnabled():
            return

        async def job_ask():
            answer = await ask(
                "Board is locked. Do you want to unlock it?",
                "You will be able to manipulate the board again.",
                ["No", "Yes"],
            )
            if answer in (0, 1):
                return
            self.board.setEnabled(True)

        asyncio.create_task(job_ask())

    async def boot(self):
        # ■■■■■ Do basic Qt things ■■■■■

        self.setupUi(self)
        self.setMouseTracking(True)

        # ■■■■■ Basic sizing ■■■■■

        self.resize(0, 0)  # To smallest size possible
        self.splitter.setSizes([3, 1, 1, 2])
        self.splitter_2.setSizes([3, 1, 1, 2])

        # ■■■■■ Hide some of the main widgets ■■■■■

        self.gauge.hide()
        self.board.hide()

        # ■■■■■ Show the window ■■■■■

        self.show()

        # ■■■■■ Global settings of packages ■■■■■

        os.get_terminal_size = lambda *args: os.terminal_size((150, 90))
        pd.set_option("display.precision", 6)
        pd.set_option("display.min_rows", 100)
        pd.set_option("display.max_rows", 100)
        pyqtgraph.setConfigOptions(antialias=True)

        # ■■■■■ Window icon ■■■■■

        filepath = PACKAGE_PATH / "static" / "product_icon.png"
        async with aiofiles.open(filepath, mode="rb") as file:
            product_icon_data = await file.read()
        product_icon_pixmap = QtGui.QPixmap()
        product_icon_pixmap.loadFromData(product_icon_data)
        self.setWindowIcon(product_icon_pixmap)

        # ■■■■■ Guide frame ■■■■■

        splash_screen = SplashScreen()
        self.centralWidget().layout().addWidget(splash_screen)

        # ■■■■■ Request internet connection ■■■■■

        asyncio.create_task(monitor_internet())
        await is_internet_checked.wait()
        while not internet_connected():
            await ask(
                "No internet connection",
                "Internet connection is necessary for Solie to start up.",
                ["Okay"],
            )
            await asyncio.sleep(1)

        # ■■■■■ Get datapath ■■■■■

        datapath = await read_datapath()

        if not datapath:
            overlay_widget = await overlay(
                "Choose your data folder",
                DatapathInput(),
                False,
            )
            datapath = overlay_widget.result
            await save_datapath(datapath)

        self.datapath = datapath

        # ■■■■■ Get data settings ■■■■■

        data_settings = await read_data_settings(datapath)

        if not data_settings:
            overlay_widget = await overlay(
                "Choose a token to treat as your asset",
                TokenSelection(),
                False,
            )
            asset_token = overlay_widget.result
            overlay_widget = await overlay(
                "Choose coins to observe and trade",
                CoinSelection(asset_token),
                False,
            )
            target_symbols = overlay_widget.result
            data_settings = DataSettings(
                asset_token=asset_token,
                target_symbols=target_symbols,
            )
            await save_data_settings(data_settings, datapath)

        self.data_settings = data_settings

        # ■■■■■ Get data settings ■■■■■

        asset_token = data_settings.asset_token
        target_symbols = data_settings.target_symbols

        # ■■■■■ Check the status of data files ■■■■■

        await examine_data_files(datapath)

        # ■■■■■ Get information about target symbols ■■■■■

        api_requester = ApiRequester()
        response = await api_requester.coingecko(
            "GET",
            "/api/v3/coins/markets",
            {
                "vs_currency": "usd",
            },
        )

        coin_names = {}
        coin_icon_urls = {}
        coin_ranks = {}

        for about_coin in response:
            coin_symbol = about_coin["symbol"].upper()
            coin_names[coin_symbol] = about_coin["name"]
            coin_icon_urls[coin_symbol] = about_coin["image"]
            coin_ranks[coin_symbol] = about_coin["market_cap_rank"]

        self.alias_to_symbol = {}
        self.symbol_to_alias = {}

        for symbol in target_symbols:
            coin_symbol = symbol.removesuffix(asset_token)
            coin_name = coin_names.get(coin_symbol, "")
            if coin_name == "":
                alias = coin_symbol
            else:
                alias = coin_name
            self.alias_to_symbol[alias] = symbol
            self.symbol_to_alias[symbol] = alias

        # ■■■■■ Make widgets according to the data_settings ■■■■■

        token_text_size = 14
        name_text_size = 11
        price_text_size = 9
        detail_text_size = 7

        is_long = len(target_symbols) > 5

        symbol_pixmaps = {}
        for symbol in target_symbols:
            coin_symbol = symbol.removesuffix(asset_token)
            coin_icon_url = coin_icon_urls.get(coin_symbol, "")
            pixmap = QtGui.QPixmap()
            if coin_icon_url != "":
                image_data = await api_requester.bytes(coin_icon_url)
                pixmap.loadFromData(image_data)
            else:
                pixmap.load(str(PACKAGE_PATH / "static" / "icon" / "blank_coin.png"))
            symbol_pixmaps[symbol] = pixmap

        token_icon_url = coin_icon_urls.get(asset_token, "")
        token_pixmap = QtGui.QPixmap()
        image_data = await api_requester.bytes(token_icon_url)
        token_pixmap.loadFromData(image_data)

        text = str(datapath)
        self.lineEdit.setText(text)
        self.lineEdit.setCursorPosition(len(text))

        icon_label = QtWidgets.QLabel()
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(token_pixmap)
        icon_label.setScaledContents(True)
        icon_label.setFixedSize(30, 30)
        this_layout = QtWidgets.QHBoxLayout()
        self.verticalLayout_14.addLayout(this_layout)
        this_layout.addWidget(icon_label)
        token_font = QtGui.QFont()
        token_font.setPointSize(token_text_size)
        token_font.setWeight(QtGui.QFont.Weight.Bold)
        token_label = QtWidgets.QLabel()
        token_label.setText(asset_token)
        token_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        token_label.setFont(token_font)
        self.verticalLayout_14.addWidget(token_label)
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(1)
        spacing_text.setFont(spacing_text_font)
        self.verticalLayout_14.addWidget(spacing_text)
        this_layout = QtWidgets.QHBoxLayout()
        self.verticalLayout_14.addLayout(this_layout)
        divider = HorizontalDivider(self)
        divider.setFixedWidth(320)
        this_layout.addWidget(divider)
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(2)
        spacing_text.setFont(spacing_text_font)
        self.verticalLayout_14.addWidget(spacing_text)

        for symbol in target_symbols:
            icon = QtGui.QIcon()
            icon.addPixmap(symbol_pixmaps[symbol])
            alias = self.symbol_to_alias[symbol]
            self.comboBox_4.addItem(icon, alias)
            self.comboBox_6.addItem(icon, alias)

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.horizontalLayout_20.addItem(spacer)
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.horizontalLayout_17.addItem(spacer)
        for turn, symbol in enumerate(target_symbols):
            coin_symbol = symbol.removesuffix(asset_token)
            coin_rank = coin_ranks.get(coin_symbol, 0)
            symbol_box = SymbolBox()
            if is_long and turn + 1 > math.floor(len(target_symbols) / 2):
                self.horizontalLayout_17.addWidget(symbol_box)
            else:
                self.horizontalLayout_20.addWidget(symbol_box)
            inside_layout = QtWidgets.QVBoxLayout(symbol_box)
            spacer = QtWidgets.QSpacerItem(
                0,
                0,
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            inside_layout.addItem(spacer)
            icon_label = QtWidgets.QLabel()
            icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            this_layout = QtWidgets.QHBoxLayout()
            inside_layout.addLayout(this_layout)
            icon_label.setPixmap(symbol_pixmaps[symbol])
            icon_label.setScaledContents(True)
            icon_label.setFixedSize(50, 50)
            icon_label.setMargin(5)
            this_layout.addWidget(icon_label)
            name_label = QtWidgets.QLabel()
            name_label.setText(self.symbol_to_alias[symbol])
            name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            name_font = QtGui.QFont()
            name_font.setPointSize(name_text_size)
            name_font.setWeight(QtGui.QFont.Weight.Bold)
            name_label.setFont(name_font)
            inside_layout.addWidget(name_label)
            price_label = QtWidgets.QLabel()
            price_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            price_font = QtGui.QFont()
            price_font.setPointSize(price_text_size)
            price_font.setWeight(QtGui.QFont.Weight.Bold)
            price_label.setFont(price_font)
            inside_layout.addWidget(price_label)
            if coin_rank == 0:
                text = coin_symbol
            else:
                text = f"{coin_rank} - {coin_symbol}"
            detail_label = QtWidgets.QLabel()
            detail_label.setText(text)
            detail_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            detail_font = QtGui.QFont()
            detail_font.setPointSize(detail_text_size)
            detail_font.setWeight(QtGui.QFont.Weight.Bold)
            detail_label.setFont(detail_font)
            inside_layout.addWidget(detail_label)
            self.price_labels[symbol] = price_label
            spacer = QtWidgets.QSpacerItem(
                0,
                0,
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            inside_layout.addItem(spacer)
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.horizontalLayout_20.addItem(spacer)
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.horizontalLayout_17.addItem(spacer)

        # ■■■■■ Show product icon and title ■■■■■

        this_layout = self.horizontalLayout_13
        product_icon_pixmap = QtGui.QPixmap()
        filepath = PACKAGE_PATH / "static" / "product_icon.png"
        async with aiofiles.open(filepath, mode="rb") as file:
            product_icon_data = await file.read()
        product_icon_pixmap.loadFromData(product_icon_data)
        product_icon_label = QtWidgets.QLabel("", self)
        product_icon_label.setPixmap(product_icon_pixmap)
        product_icon_label.setScaledContents(True)
        product_icon_label.setFixedSize(80, 80)
        this_layout.addWidget(product_icon_label)
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(8)
        spacing_text.setFont(spacing_text_font)
        this_layout.addWidget(spacing_text)
        title_label = BrandLabel(self, "SOLIE", 48)
        this_layout.addWidget(title_label)
        text = PACKAGE_VERSION
        label = BrandLabel(self, text, 24)
        this_layout.addWidget(label)

        # ■■■■■ Transaction graph widgets ■■■■■

        self.plot_widget.setBackground("#252525")
        self.plot_widget_1.setBackground("#252525")
        self.plot_widget_4.setBackground("#252525")
        self.plot_widget_6.setBackground("#252525")
        self.plot_widget.setMouseEnabled(y=False)
        self.plot_widget_1.setMouseEnabled(y=False)
        self.plot_widget_4.setMouseEnabled(y=False)
        self.plot_widget_6.setMouseEnabled(y=False)
        self.plot_widget.enableAutoRange(y=True)
        self.plot_widget_1.enableAutoRange(y=True)
        self.plot_widget_4.enableAutoRange(y=True)
        self.plot_widget_6.enableAutoRange(y=True)
        self.horizontalLayout_7.addWidget(self.plot_widget)
        self.horizontalLayout_29.addWidget(self.plot_widget_1)
        self.horizontalLayout_16.addWidget(self.plot_widget_4)
        self.horizontalLayout_28.addWidget(self.plot_widget_6)

        plot_item: pyqtgraph.PlotItem = self.plot_widget.plotItem
        plot_item_1 = self.plot_widget_1.plotItem
        plot_item_4 = self.plot_widget_4.plotItem
        plot_item_6 = self.plot_widget_6.plotItem

        if plot_item is None:
            raise ValueError("Plot item was none")
        if plot_item_1 is None:
            raise ValueError("Plot item was none")
        if plot_item_4 is None:
            raise ValueError("Plot item was none")
        if plot_item_6 is None:
            raise ValueError("Plot item was none")

        plot_item.vb.setLimits(xMin=0, yMin=0)  # type:ignore
        plot_item_1.vb.setLimits(xMin=0, yMin=0)  # type:ignore
        plot_item_4.vb.setLimits(xMin=0, yMin=0)  # type:ignore
        plot_item_6.vb.setLimits(xMin=0)  # type:ignore
        plot_item.setDownsampling(auto=True, mode="subsample")
        plot_item.setClipToView(True)
        plot_item.setAutoVisible(y=True)
        plot_item_1.setDownsampling(auto=True, mode="subsample")
        plot_item_1.setClipToView(True)
        plot_item_1.setAutoVisible(y=True)
        plot_item_4.setDownsampling(auto=True, mode="subsample")
        plot_item_4.setClipToView(True)
        plot_item_4.setAutoVisible(y=True)
        plot_item_6.setDownsampling(auto=True, mode="subsample")
        plot_item_6.setClipToView(True)
        plot_item_6.setAutoVisible(y=True)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": PercentAxisItem(orientation="left"),
            "right": PercentAxisItem(orientation="right"),
        }
        plot_item.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": PercentAxisItem(orientation="left"),
            "right": PercentAxisItem(orientation="right"),
        }
        plot_item_1.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": pyqtgraph.AxisItem(orientation="left"),
            "right": pyqtgraph.AxisItem(orientation="right"),
        }
        plot_item_4.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": pyqtgraph.AxisItem(orientation="left"),
            "right": pyqtgraph.AxisItem(orientation="right"),
        }
        plot_item_6.setAxisItems(axis_items)
        tick_font = QtGui.QFont("Source Code Pro", 7)
        plot_item.getAxis("top").setTickFont(tick_font)
        plot_item.getAxis("bottom").setTickFont(tick_font)
        plot_item.getAxis("left").setTickFont(tick_font)
        plot_item.getAxis("right").setTickFont(tick_font)
        plot_item_1.getAxis("top").setTickFont(tick_font)
        plot_item_1.getAxis("bottom").setTickFont(tick_font)
        plot_item_1.getAxis("left").setTickFont(tick_font)
        plot_item_1.getAxis("right").setTickFont(tick_font)
        plot_item_4.getAxis("top").setTickFont(tick_font)
        plot_item_4.getAxis("bottom").setTickFont(tick_font)
        plot_item_4.getAxis("left").setTickFont(tick_font)
        plot_item_4.getAxis("right").setTickFont(tick_font)
        plot_item_6.getAxis("top").setTickFont(tick_font)
        plot_item_6.getAxis("bottom").setTickFont(tick_font)
        plot_item_6.getAxis("left").setTickFont(tick_font)
        plot_item_6.getAxis("right").setTickFont(tick_font)
        plot_item.getAxis("left").setWidth(40)
        plot_item.getAxis("right").setWidth(40)
        plot_item_1.getAxis("left").setWidth(40)
        plot_item_1.getAxis("right").setWidth(40)
        plot_item_4.getAxis("left").setWidth(40)
        plot_item_4.getAxis("right").setWidth(40)
        plot_item_6.getAxis("left").setWidth(40)
        plot_item_6.getAxis("right").setWidth(40)
        plot_item.getAxis("bottom").setHeight(0)
        plot_item_1.getAxis("top").setHeight(0)
        plot_item_4.getAxis("top").setHeight(0)
        plot_item_4.getAxis("bottom").setHeight(0)
        plot_item_6.getAxis("top").setHeight(0)
        plot_item_6.getAxis("bottom").setHeight(0)
        plot_item.showGrid(x=True, y=True, alpha=0.1)
        plot_item_1.showGrid(x=True, y=True, alpha=0.1)
        plot_item_4.showGrid(x=True, y=True, alpha=0.1)
        plot_item_6.showGrid(x=True, y=True, alpha=0.1)

        self.transaction_lines["book_tickers"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen("#3F3F3F"),
                connect="finite",
                stepMode="right",
            )
            for _ in range(2)
        ]
        self.transaction_lines["last_price"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen("#5A8CC2"),
                connect="finite",
                stepMode="right",
            )
        ]
        self.transaction_lines["mark_price"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen("#3E628A"),
                connect="finite",
            )
        ]
        self.transaction_lines["price_indicators"] = [
            plot_item.plot(connect="finite") for _ in range(20)
        ]
        self.transaction_lines["entry_price"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen("#FFBB00"),
                connect="finite",
            )
        ]
        self.transaction_lines["wobbles"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen("#888888"),
                connect="finite",
                stepMode="right",
            )
            for _ in range(2)
        ]
        self.transaction_lines["price_rise"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen("#70E161"),
                connect="finite",
            )
        ]
        self.transaction_lines["price_fall"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen("#FF304F"),
                connect="finite",
            )
        ]
        self.transaction_lines["price_stay"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen("#DDDDDD"),
                connect="finite",
            )
        ]
        self.transaction_lines["sell"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen(None),  # invisible line
                symbol="o",
                symbolBrush="#0055FF",
                symbolPen=pyqtgraph.mkPen("#BBBBBB"),
                symbolSize=8,
            )
        ]
        self.transaction_lines["buy"] = [
            plot_item.plot(
                pen=pyqtgraph.mkPen(None),  # invisible line
                symbol="o",
                symbolBrush="#FF3300",
                symbolPen=pyqtgraph.mkPen("#BBBBBB"),
                symbolSize=8,
            )
        ]
        self.transaction_lines["volume"] = [
            plot_item_4.plot(
                pen=pyqtgraph.mkPen("#BBBBBB"),
                connect="all",
                stepMode="right",
                fillLevel=0,
                brush=pyqtgraph.mkBrush(255, 255, 255, 15),
            )
        ]
        self.transaction_lines["last_volume"] = [
            plot_item_4.plot(
                pen=pyqtgraph.mkPen("#BBBBBB"),
                connect="finite",
            )
        ]
        self.transaction_lines["volume_indicators"] = [
            plot_item_4.plot(connect="finite") for _ in range(20)
        ]
        self.transaction_lines["abstract_indicators"] = [
            plot_item_6.plot(connect="finite") for _ in range(20)
        ]
        self.transaction_lines["asset_with_unrealized_profit"] = [
            plot_item_1.plot(
                pen=pyqtgraph.mkPen("#999999"),
                connect="finite",
            )
        ]
        self.transaction_lines["asset"] = [
            plot_item_1.plot(
                pen=pyqtgraph.mkPen("#FF8700"),
                connect="finite",
                stepMode="right",
            )
        ]

        self.plot_widget_1.setXLink(self.plot_widget)
        self.plot_widget_4.setXLink(self.plot_widget_1)
        self.plot_widget_6.setXLink(self.plot_widget_4)

        # ■■■■■ Simulation graph widgets ■■■■■

        self.plot_widget_2.setBackground("#252525")
        self.plot_widget_3.setBackground("#252525")
        self.plot_widget_5.setBackground("#252525")
        self.plot_widget_7.setBackground("#252525")
        self.plot_widget_2.setMouseEnabled(y=False)
        self.plot_widget_3.setMouseEnabled(y=False)
        self.plot_widget_5.setMouseEnabled(y=False)
        self.plot_widget_7.setMouseEnabled(y=False)
        self.plot_widget_2.enableAutoRange(y=True)
        self.plot_widget_3.enableAutoRange(y=True)
        self.plot_widget_5.enableAutoRange(y=True)
        self.plot_widget_7.enableAutoRange(y=True)
        self.horizontalLayout.addWidget(self.plot_widget_2)
        self.horizontalLayout_30.addWidget(self.plot_widget_3)
        self.horizontalLayout_19.addWidget(self.plot_widget_5)
        self.horizontalLayout_31.addWidget(self.plot_widget_7)

        plot_item_2 = self.plot_widget_2.plotItem
        plot_item_3 = self.plot_widget_3.plotItem
        plot_item_5 = self.plot_widget_5.plotItem
        plot_item_7 = self.plot_widget_7.plotItem

        if plot_item_2 is None:
            raise ValueError("Plot item was none")
        if plot_item_3 is None:
            raise ValueError("Plot item was none")
        if plot_item_5 is None:
            raise ValueError("Plot item was none")
        if plot_item_7 is None:
            raise ValueError("Plot item was none")

        plot_item_2.vb.setLimits(xMin=0, yMin=0)  # type:ignore
        plot_item_3.vb.setLimits(xMin=0, yMin=0)  # type:ignore
        plot_item_5.vb.setLimits(xMin=0, yMin=0)  # type:ignore
        plot_item_7.vb.setLimits(xMin=0)  # type:ignore
        plot_item_2.setDownsampling(auto=True, mode="subsample")
        plot_item_2.setClipToView(True)
        plot_item_2.setAutoVisible(y=True)
        plot_item_3.setDownsampling(auto=True, mode="subsample")
        plot_item_3.setClipToView(True)
        plot_item_3.setAutoVisible(y=True)
        plot_item_5.setDownsampling(auto=True, mode="subsample")
        plot_item_5.setClipToView(True)
        plot_item_5.setAutoVisible(y=True)
        plot_item_7.setDownsampling(auto=True, mode="subsample")
        plot_item_7.setClipToView(True)
        plot_item_7.setAutoVisible(y=True)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": PercentAxisItem(orientation="left"),
            "right": PercentAxisItem(orientation="right"),
        }
        plot_item_2.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": PercentAxisItem(orientation="left"),
            "right": PercentAxisItem(orientation="right"),
        }
        plot_item_3.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": pyqtgraph.AxisItem(orientation="left"),
            "right": pyqtgraph.AxisItem(orientation="right"),
        }
        plot_item_5.setAxisItems(axis_items)
        axis_items = {
            "top": TimeAxisItem(orientation="top"),
            "bottom": TimeAxisItem(orientation="bottom"),
            "left": pyqtgraph.AxisItem(orientation="left"),
            "right": pyqtgraph.AxisItem(orientation="right"),
        }
        plot_item_7.setAxisItems(axis_items)
        tick_font = QtGui.QFont("Source Code Pro", 7)
        plot_item_2.getAxis("top").setTickFont(tick_font)
        plot_item_2.getAxis("bottom").setTickFont(tick_font)
        plot_item_2.getAxis("left").setTickFont(tick_font)
        plot_item_2.getAxis("right").setTickFont(tick_font)
        plot_item_3.getAxis("top").setTickFont(tick_font)
        plot_item_3.getAxis("bottom").setTickFont(tick_font)
        plot_item_3.getAxis("left").setTickFont(tick_font)
        plot_item_3.getAxis("right").setTickFont(tick_font)
        plot_item_5.getAxis("top").setTickFont(tick_font)
        plot_item_5.getAxis("bottom").setTickFont(tick_font)
        plot_item_5.getAxis("left").setTickFont(tick_font)
        plot_item_5.getAxis("right").setTickFont(tick_font)
        plot_item_7.getAxis("top").setTickFont(tick_font)
        plot_item_7.getAxis("bottom").setTickFont(tick_font)
        plot_item_7.getAxis("left").setTickFont(tick_font)
        plot_item_7.getAxis("right").setTickFont(tick_font)
        plot_item_2.getAxis("left").setWidth(40)
        plot_item_2.getAxis("right").setWidth(40)
        plot_item_3.getAxis("left").setWidth(40)
        plot_item_3.getAxis("right").setWidth(40)
        plot_item_5.getAxis("left").setWidth(40)
        plot_item_5.getAxis("right").setWidth(40)
        plot_item_7.getAxis("left").setWidth(40)
        plot_item_7.getAxis("right").setWidth(40)
        plot_item_2.getAxis("bottom").setHeight(0)
        plot_item_3.getAxis("top").setHeight(0)
        plot_item_5.getAxis("top").setHeight(0)
        plot_item_5.getAxis("bottom").setHeight(0)
        plot_item_7.getAxis("top").setHeight(0)
        plot_item_7.getAxis("bottom").setHeight(0)
        plot_item_2.showGrid(x=True, y=True, alpha=0.1)
        plot_item_3.showGrid(x=True, y=True, alpha=0.1)
        plot_item_5.showGrid(x=True, y=True, alpha=0.1)
        plot_item_7.showGrid(x=True, y=True, alpha=0.1)

        self.simulation_lines["book_tickers"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen("#3F3F3F"),
                connect="finite",
                stepMode="right",
            )
            for _ in range(2)
        ]
        self.simulation_lines["last_price"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen("#5A8CC2"),
                connect="finite",
                stepMode="right",
            )
        ]
        self.simulation_lines["mark_price"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen("#3E628A"),
                connect="finite",
            )
        ]
        self.simulation_lines["price_indicators"] = [
            plot_item_2.plot(connect="finite") for _ in range(20)
        ]
        self.simulation_lines["entry_price"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen("#FFBB00"),
                connect="finite",
            )
        ]
        self.simulation_lines["wobbles"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen("#888888"),
                connect="finite",
                stepMode="right",
            )
            for _ in range(2)
        ]
        self.simulation_lines["price_rise"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen("#70E161"),
                connect="finite",
            )
        ]
        self.simulation_lines["price_fall"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen("#FF304F"),
                connect="finite",
            )
        ]
        self.simulation_lines["price_stay"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen("#DDDDDD"),
                connect="finite",
            )
        ]
        self.simulation_lines["sell"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen(None),  # invisible line
                symbol="o",
                symbolBrush="#0055FF",
                symbolPen=pyqtgraph.mkPen("#BBBBBB"),
                symbolSize=8,
            )
        ]
        self.simulation_lines["buy"] = [
            plot_item_2.plot(
                pen=pyqtgraph.mkPen(None),  # invisible line
                symbol="o",
                symbolBrush="#FF3300",
                symbolPen=pyqtgraph.mkPen("#BBBBBB"),
                symbolSize=8,
            )
        ]
        self.simulation_lines["volume"] = [
            plot_item_5.plot(
                pen=pyqtgraph.mkPen("#BBBBBB"),
                connect="all",
                stepMode="right",
                fillLevel=0,
                brush=pyqtgraph.mkBrush(255, 255, 255, 15),
            )
        ]
        self.simulation_lines["last_volume"] = [
            plot_item_5.plot(
                pen=pyqtgraph.mkPen("#BBBBBB"),
                connect="finite",
            )
        ]
        self.simulation_lines["volume_indicators"] = [
            plot_item_5.plot(connect="finite") for _ in range(20)
        ]
        self.simulation_lines["abstract_indicators"] = [
            plot_item_7.plot(connect="finite") for _ in range(20)
        ]
        self.simulation_lines["asset_with_unrealized_profit"] = [
            plot_item_3.plot(
                pen=pyqtgraph.mkPen("#999999"),
                connect="finite",
            )
        ]
        self.simulation_lines["asset"] = [
            plot_item_3.plot(
                pen=pyqtgraph.mkPen("#FF8700"),
                connect="finite",
                stepMode="right",
            )
        ]

        self.plot_widget_3.setXLink(self.plot_widget_2)
        self.plot_widget_5.setXLink(self.plot_widget_3)
        self.plot_widget_7.setXLink(self.plot_widget_5)

        # ■■■■■ Prepare logging ■■■■■

        def log_callback(summarization: str, log_content: str):
            self.listWidget.add_item(summarization, log_content)

        log_path = datapath / "+logs"
        await aiofiles.os.makedirs(log_path, exist_ok=True)
        log_handler = LogHandler(log_path, log_callback)
        logging.root.addHandler(log_handler)

        # ■■■■■ Start repetitive timer ■■■■■

        self.scheduler.start()

        # ■■■■■ Wait until the contents are filled ■■■■■

        await asyncio.sleep(1)

        # ■■■■■ Change closing behavior ■■■■■

        self.should_finalize = True
        self.should_confirm_closing = True

        # ■■■■■ Show main widgets ■■■■■

        splash_screen.setParent(None)
        self.board.show()
        self.gauge.show()

    async def process_ui_events(self):
        interval = 1 / 240
        app_instance = QtCore.QCoreApplication.instance()
        if app_instance is None:
            raise ValueError("App instance is none, cannot process events")
        while True:
            app_instance.processEvents()
            await asyncio.sleep(interval)
