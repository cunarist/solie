import asyncio
import logging
import math
import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Coroutine

import aiofiles
import pandas as pd
import pyqtgraph
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6 import QtCore, QtGui, QtWidgets
from qasync import QEventLoop

from module import introduction
from module.instrument.api_requester import ApiRequester
from module.instrument.log_handler import LogHandler
from module.instrument.percent_axis_item import PercentAxisItem
from module.instrument.time_axis_item import TimeAxisItem
from module.recipe import check_internet, examine_data_files, outsource, user_settings
from module.shelf.coin_selection import CoinSelection
from module.shelf.datapath_input import DatapathInput
from module.shelf.token_selection import TokenSelection
from module.user_interface import Ui_MainWindow
from module.widget.ask_popup import AskPopup
from module.widget.brand_label import BrandLabel
from module.widget.horizontal_divider import HorizontalDivider
from module.widget.overlap_popup import OverlapPopup
from module.widget.splash_screen import SplashScreen
from module.widget.symbol_box import SymbolBox
from module.worker import collector, manager, simulator, strategist, transactor


class Window(QtWidgets.QMainWindow, Ui_MainWindow):
    def closeEvent(self, event):  # noqa:N802
        event.ignore()

        async def job_close():
            if not self.should_finalize:
                app_close_event.set()

            if self.should_confirm_closing:
                question = [
                    "Really quit?",
                    "If Solie is not turned on, data collection gets stopped as well."
                    " Solie will proceed to finalizations such as closing network"
                    " connections and saving data.",
                    ["Cancel", "Shut down"],
                ]
                answer = await self.ask(question)

                if answer in (0, 1):
                    return

            AskPopup.done_event.set()
            OverlapPopup.done_event.set()

            self.gauge.hide()
            self.board.hide()
            self.closeEvent = lambda event: event.ignore()

            splash_screen = SplashScreen()
            self.centralWidget().layout().addWidget(splash_screen)

            self.scheduler.shutdown()
            await asyncio.sleep(1)

            self.should_overlap_error = True
            await asyncio.gather(
                *[finalize_function() for finalize_function in self.finalize_functions],
                return_exceptions=True,
            )

            app_close_event.set()

        asyncio.create_task(job_close())

    def mouseMoveEvent(self, event):  # noqa:N802
        self.last_interaction = datetime.now(timezone.utc)

    def mousePressEvent(self, event):  # noqa:N802
        self.last_interaction = datetime.now(timezone.utc)

    def mouseReleaseEvent(self, event):  # noqa:N802
        self.last_interaction = datetime.now(timezone.utc)
        is_enabled = self.board.isEnabled()
        if is_enabled:
            return

        async def job_ask():
            question = [
                "Board is locked. Do you want to unlock it?",
                "You will be able to manipulate the board again.",
                ["No", "Yes"],
            ]
            answer = await self.ask(question)
            if answer in (0, 1):
                return
            self.board.setEnabled(True)

        asyncio.create_task(job_ask())

    def __init__(self):
        super().__init__()
        self.price_labels = {}
        self.last_interaction = datetime.now(timezone.utc)

        self.plot_widget = pyqtgraph.PlotWidget()
        self.plot_widget_1 = pyqtgraph.PlotWidget()
        self.plot_widget_4 = pyqtgraph.PlotWidget()
        self.plot_widget_6 = pyqtgraph.PlotWidget()

        self.plot_widget_2 = pyqtgraph.PlotWidget()
        self.plot_widget_3 = pyqtgraph.PlotWidget()
        self.plot_widget_5 = pyqtgraph.PlotWidget()
        self.plot_widget_7 = pyqtgraph.PlotWidget()

        self.transaction_lines: dict[str, pyqtgraph.PlotDataItem] = {}
        self.simulation_lines: dict[str, pyqtgraph.PlotDataItem] = {}

        self.collector: collector.Collector
        self.transactor: transactor.Transactor
        self.simulator: simulator.Simulator
        self.strategist: strategist.Strategiest
        self.manager: manager.Manager

        self.initialize_functions: list[Callable[..., Coroutine]] = []
        self.finalize_functions: list[Callable[..., Coroutine]] = []
        self.scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "max_instances": 2,
            },
        )

        # ■■■■■ do basic Qt things ■■■■■

        self.setupUi(self)
        self.setMouseTracking(True)

        # ■■■■■ basic sizing ■■■■■

        self.resize(0, 0)  # to smallest size possible
        self.splitter.setSizes([3, 1, 1, 2])
        self.splitter_2.setSizes([3, 1, 1, 2])

        # ■■■■■ app behavior settings ■■■■■

        self.should_finalize = False
        self.should_confirm_closing = True
        self.should_overlap_error = True
        self.last_interaction = datetime.now(timezone.utc)

        # ■■■■■ hide some of the main widgets ■■■■■

        self.gauge.hide()
        self.board.hide()

    async def boot(self):
        # ■■■■■ global settings of packages ■■■■■

        os.get_terminal_size = lambda *args: os.terminal_size((150, 90))
        pd.set_option("display.precision", 6)
        pd.set_option("display.min_rows", 100)
        pd.set_option("display.max_rows", 100)
        pyqtgraph.setConfigOptions(antialias=True)
        logging.getLogger().addHandler(LogHandler())

        # ■■■■■ guide frame ■■■■■

        splash_screen = SplashScreen()
        self.centralWidget().layout().addWidget(splash_screen)

        # ■■■■■ start basic things ■■■■■

        await user_settings.load()
        await examine_data_files.do()
        await user_settings.load()
        asyncio.create_task(check_internet.monitor())

        # ■■■■■ request internet connection ■■■■■

        await check_internet.is_ready.wait()
        while not check_internet.connected():
            question = [
                "No internet connection",
                "Internet connection is necessary for Solie to start up.",
                ["Okay"],
            ]
            await self.ask(question)
            await asyncio.sleep(1)

        # ■■■■■ check app settings ■■■■■

        if user_settings.get_app_settings()["datapath"] is None:
            formation = [
                "Choose your data folder",
                DatapathInput,
                False,
                None,
            ]
            await self.overlap(formation)

        # ■■■■■ check data settings ■■■■■

        if user_settings.get_data_settings()["asset_token"] is None:
            formation = [
                "Choose a token to treat as your asset",
                TokenSelection,
                False,
                None,
            ]
            await self.overlap(formation)

        if user_settings.get_data_settings()["target_symbols"] is None:
            formation = [
                "Choose coins",
                CoinSelection,
                False,
                None,
            ]
            await self.overlap(formation)

        # ■■■■■ get information about target symbols ■■■■■

        api_requester = ApiRequester()

        asset_token = user_settings.get_data_settings()["asset_token"]
        target_symbols = user_settings.get_data_settings()["target_symbols"]
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

        # ■■■■■ make widgets according to the data_settings ■■■■■

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
                pixmap.load("./static/icon/blank_coin.png")
            symbol_pixmaps[symbol] = pixmap

        token_icon_url = coin_icon_urls.get(asset_token, "")
        token_pixmap = QtGui.QPixmap()
        image_data = await api_requester.bytes(token_icon_url)
        token_pixmap.loadFromData(image_data)

        text = user_settings.get_app_settings()["datapath"]
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

        # ■■■■■ show product icon and title ■■■■■

        this_layout = self.horizontalLayout_13
        product_icon_pixmap = QtGui.QPixmap()
        async with aiofiles.open("./static/product_icon.png", mode="rb") as file:
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
        text = introduction.CURRENT_VERSION
        label = BrandLabel(self, text, 24)
        this_layout.addWidget(label)

        # ■■■■■ transaction graph widgets ■■■■■

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

        self.transaction_lines = {
            "book_tickers": [
                plot_item.plot(
                    pen=pyqtgraph.mkPen("#3F3F3F"),
                    connect="finite",
                    stepMode="right",
                )
                for _ in range(2)
            ],
            "last_price": plot_item.plot(
                pen=pyqtgraph.mkPen("#5A8CC2"),
                connect="finite",
                stepMode="right",
            ),
            "mark_price": plot_item.plot(
                pen=pyqtgraph.mkPen("#3E628A"),
                connect="finite",
            ),
            "price_indicators": [plot_item.plot(connect="finite") for _ in range(20)],
            "entry_price": plot_item.plot(
                pen=pyqtgraph.mkPen("#FFBB00"),
                connect="finite",
            ),
            "wobbles": [
                plot_item.plot(
                    pen=pyqtgraph.mkPen("#888888"),
                    connect="finite",
                    stepMode="right",
                )
                for _ in range(2)
            ],
            "price_rise": plot_item.plot(
                pen=pyqtgraph.mkPen("#70E161"),
                connect="finite",
            ),
            "price_fall": plot_item.plot(
                pen=pyqtgraph.mkPen("#FF304F"),
                connect="finite",
            ),
            "price_stay": plot_item.plot(
                pen=pyqtgraph.mkPen("#DDDDDD"),
                connect="finite",
            ),
            "sell": plot_item.plot(
                pen=pyqtgraph.mkPen(None),  # invisible line
                symbol="o",
                symbolBrush="#0055FF",
                symbolPen=pyqtgraph.mkPen("#BBBBBB"),
                symbolSize=8,
            ),
            "buy": plot_item.plot(
                pen=pyqtgraph.mkPen(None),  # invisible line
                symbol="o",
                symbolBrush="#FF3300",
                symbolPen=pyqtgraph.mkPen("#BBBBBB"),
                symbolSize=8,
            ),
            "volume": plot_item_4.plot(
                pen=pyqtgraph.mkPen("#BBBBBB"),
                connect="all",
                stepMode="right",
                fillLevel=0,
                brush=pyqtgraph.mkBrush(255, 255, 255, 15),
            ),
            "last_volume": plot_item_4.plot(
                pen=pyqtgraph.mkPen("#BBBBBB"),
                connect="finite",
            ),
            "volume_indicators": [
                plot_item_4.plot(connect="finite") for _ in range(20)
            ],
            "abstract_indicators": [
                plot_item_6.plot(connect="finite") for _ in range(20)
            ],
            "asset_with_unrealized_profit": plot_item_1.plot(
                pen=pyqtgraph.mkPen("#999999"),
                connect="finite",
            ),
            "asset": plot_item_1.plot(
                pen=pyqtgraph.mkPen("#FF8700"),
                connect="finite",
                stepMode="right",
            ),
        }

        self.plot_widget_1.setXLink(self.plot_widget)
        self.plot_widget_4.setXLink(self.plot_widget_1)
        self.plot_widget_6.setXLink(self.plot_widget_4)

        # ■■■■■ simulation graph widgets ■■■■■

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

        self.simulation_lines = {
            "book_tickers": [
                plot_item_2.plot(
                    pen=pyqtgraph.mkPen("#3F3F3F"),
                    connect="finite",
                    stepMode="right",
                )
                for _ in range(2)
            ],
            "last_price": plot_item_2.plot(
                pen=pyqtgraph.mkPen("#5A8CC2"),
                connect="finite",
                stepMode="right",
            ),
            "mark_price": plot_item_2.plot(
                pen=pyqtgraph.mkPen("#3E628A"),
                connect="finite",
            ),
            "price_indicators": [plot_item_2.plot(connect="finite") for _ in range(20)],
            "entry_price": plot_item_2.plot(
                pen=pyqtgraph.mkPen("#FFBB00"),
                connect="finite",
            ),
            "wobbles": [
                plot_item_2.plot(
                    pen=pyqtgraph.mkPen("#888888"),
                    connect="finite",
                    stepMode="right",
                )
                for _ in range(2)
            ],
            "price_rise": plot_item_2.plot(
                pen=pyqtgraph.mkPen("#70E161"),
                connect="finite",
            ),
            "price_fall": plot_item_2.plot(
                pen=pyqtgraph.mkPen("#FF304F"),
                connect="finite",
            ),
            "price_stay": plot_item_2.plot(
                pen=pyqtgraph.mkPen("#DDDDDD"),
                connect="finite",
            ),
            "sell": plot_item_2.plot(
                pen=pyqtgraph.mkPen(None),  # invisible line
                symbol="o",
                symbolBrush="#0055FF",
                symbolPen=pyqtgraph.mkPen("#BBBBBB"),
                symbolSize=8,
            ),
            "buy": plot_item_2.plot(
                pen=pyqtgraph.mkPen(None),  # invisible line
                symbol="o",
                symbolBrush="#FF3300",
                symbolPen=pyqtgraph.mkPen("#BBBBBB"),
                symbolSize=8,
            ),
            "volume": plot_item_5.plot(
                pen=pyqtgraph.mkPen("#BBBBBB"),
                connect="all",
                stepMode="right",
                fillLevel=0,
                brush=pyqtgraph.mkBrush(255, 255, 255, 15),
            ),
            "last_volume": plot_item_5.plot(
                pen=pyqtgraph.mkPen("#BBBBBB"),
                connect="finite",
            ),
            "volume_indicators": [
                plot_item_5.plot(connect="finite") for _ in range(20)
            ],
            "abstract_indicators": [
                plot_item_7.plot(connect="finite") for _ in range(20)
            ],
            "asset_with_unrealized_profit": plot_item_3.plot(
                pen=pyqtgraph.mkPen("#999999"),
                connect="finite",
            ),
            "asset": plot_item_3.plot(
                pen=pyqtgraph.mkPen("#FF8700"),
                connect="finite",
                stepMode="right",
            ),
        }

        self.plot_widget_3.setXLink(self.plot_widget_2)
        self.plot_widget_5.setXLink(self.plot_widget_3)
        self.plot_widget_7.setXLink(self.plot_widget_5)

        # ■■■■■ workers ■■■■■

        self.collector = collector.Collector()
        self.transactor = transactor.Transactor()
        self.simulator = simulator.Simulator()
        self.strategist = strategist.Strategiest()
        self.manager = manager.Manager()

        # ■■■■■ initialize functions ■■■■■

        self.initialize_functions = [
            self.collector.load,
            self.transactor.load,
            self.simulator.load,
            self.strategist.load,
            self.manager.load,
        ]

        # ■■■■■ finalize functions ■■■■■

        self.finalize_functions = [
            self.transactor.save_large_data,
            self.transactor.save_scribbles,
            self.strategist.save_strategies,
            self.collector.save_candle_data,
        ]

        # ■■■■■ change logging settings ■■■■■

        self.should_overlap_error = False
        logger = logging.getLogger("solie")
        logger.setLevel("DEBUG")
        logger.info("Started up")

        # ■■■■■ connect events to functions ■■■■■

        # special widgets
        job = self.transactor.display_range_information
        outsource.do(self.plot_widget.sigRangeChanged, job)
        job = self.transactor.set_minimum_view_range
        outsource.do(self.plot_widget.sigRangeChanged, job)
        job = self.simulator.display_range_information
        outsource.do(self.plot_widget_2.sigRangeChanged, job)
        job = self.simulator.set_minimum_view_range
        outsource.do(self.plot_widget_2.sigRangeChanged, job)

        # normal widgets
        job = self.simulator.update_calculation_settings
        outsource.do(self.comboBox.currentIndexChanged, job)
        job = self.transactor.update_automation_settings
        outsource.do(self.comboBox_2.currentIndexChanged, job)
        job = self.transactor.update_automation_settings
        outsource.do(self.checkBox.toggled, job)
        job = self.simulator.calculate
        outsource.do(self.pushButton_3.clicked, job)
        job = self.manager.open_datapath
        outsource.do(self.pushButton_8.clicked, job)
        job = self.simulator.update_presentation_settings
        outsource.do(self.spinBox_2.editingFinished, job)
        job = self.simulator.update_presentation_settings
        outsource.do(self.doubleSpinBox.editingFinished, job)
        job = self.simulator.update_presentation_settings
        outsource.do(self.doubleSpinBox_2.editingFinished, job)
        job = self.simulator.erase
        outsource.do(self.pushButton_4.clicked, job)
        job = self.simulator.update_calculation_settings
        outsource.do(self.comboBox_5.currentIndexChanged, job)
        job = self.transactor.update_keys
        outsource.do(self.lineEdit_4.editingFinished, job)
        job = self.transactor.update_keys
        outsource.do(self.lineEdit_6.editingFinished, job)
        job = self.manager.run_script
        outsource.do(self.pushButton.clicked, job)
        job = self.transactor.toggle_frequent_draw
        outsource.do(self.checkBox_2.toggled, job)
        job = self.simulator.toggle_combined_draw
        outsource.do(self.checkBox_3.toggled, job)
        job = self.transactor.display_day_range
        outsource.do(self.pushButton_14.clicked, job)
        job = self.simulator.display_year_range
        outsource.do(self.pushButton_15.clicked, job)
        job = self.simulator.delete_calculation_data
        outsource.do(self.pushButton_16.clicked, job)
        job = self.simulator.draw
        outsource.do(self.pushButton_17.clicked, job)
        job = self.collector.download_fill_candle_data
        outsource.do(self.pushButton_2.clicked, job)
        job = self.transactor.update_mode_settings
        outsource.do(self.spinBox.editingFinished, job)
        job = self.manager.deselect_log_output
        outsource.do(self.pushButton_6.clicked, job)
        job = self.manager.reset_datapath
        outsource.do(self.pushButton_22.clicked, job)
        job = self.transactor.update_viewing_symbol
        outsource.do(self.comboBox_4.currentIndexChanged, job)
        job = self.simulator.update_viewing_symbol
        outsource.do(self.comboBox_6.currentIndexChanged, job)
        job = self.manager.open_documentation
        outsource.do(self.pushButton_7.clicked, job)
        job = self.strategist.add_blank_strategy
        outsource.do(self.pushButton_5.clicked, job)
        job = self.manager.change_settings
        outsource.do(self.checkBox_12.toggled, job)
        job = self.manager.change_settings
        outsource.do(self.checkBox_13.toggled, job)
        job = self.manager.change_settings
        outsource.do(self.comboBox_3.currentIndexChanged, job)
        job = self.collector.guide_donation
        outsource.do(self.pushButton_9.clicked, job)

        # ■■■■■ submenu actions ■■■■■

        action_menu = QtWidgets.QMenu(self)
        self.pushButton_13.setMenu(action_menu)
        text = "Open binance historical data webpage"
        job = self.collector.open_binance_data_page
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Stop filling candle data"
        job = self.collector.stop_filling_candle_data
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)

        action_menu = QtWidgets.QMenu(self)
        self.pushButton_12.setMenu(action_menu)
        text = "Open binance exchange"
        job = self.transactor.open_exchange
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Open binance futures wallet"
        job = self.transactor.open_futures_wallet_page
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Open binance API management webpage"
        job = self.transactor.open_api_management_page
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Clear all positions and open orders"
        job = self.transactor.clear_positions_and_open_orders
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Display same range as simulation graph"
        job = self.transactor.match_graph_range
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Show Raw Account State Object"
        job = self.transactor.show_raw_account_state_object
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)

        action_menu = QtWidgets.QMenu(self)
        self.pushButton_11.setMenu(action_menu)
        text = "Calculate temporarily only on visible range"
        job = self.simulator.simulate_only_visible
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Stop calculation"
        job = self.simulator.stop_calculation
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Find spots with lowest unrealized profit"
        job = self.simulator.analyze_unrealized_peaks
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)
        text = "Display same range as transaction graph"
        job = self.simulator.match_graph_range
        new_action = action_menu.addAction(text)
        outsource.do(new_action.triggered, job)

        # ■■■■■ initialize functions ■■■■■

        await asyncio.gather(
            *[job() for job in self.initialize_functions],
            return_exceptions=True,
        )

        # ■■■■■ start repetitive timer ■■■■■

        self.scheduler.start()

        # ■■■■■ activate finalization ■■■■■

        self.should_finalize = True

        # ■■■■■ start basic functions ■■■■■

        asyncio.create_task(self.collector.get_exchange_information())
        asyncio.create_task(self.strategist.display_strategies())
        asyncio.create_task(self.transactor.display_strategy_index())
        asyncio.create_task(self.transactor.watch_binance())
        asyncio.create_task(self.transactor.update_user_data_stream())
        asyncio.create_task(self.transactor.display_lines())
        asyncio.create_task(self.transactor.display_day_range())
        asyncio.create_task(self.simulator.display_lines())
        asyncio.create_task(self.simulator.display_year_range())
        asyncio.create_task(self.manager.check_binance_limits())
        asyncio.create_task(self.manager.display_internal_status())

        # ■■■■■ wait until the contents are filled ■■■■■

        await asyncio.sleep(1)

        # ■■■■■ show main widgets ■■■■■

        splash_screen.setParent(None)  # type:ignore
        self.board.show()
        self.gauge.show()

    # show an ask popup and blocks the stack
    async def ask(self, question):
        ask_popup = AskPopup(self, question)
        ask_popup.show()

        await ask_popup.done_event.wait()

        ask_popup.setParent(None)  # type:ignore
        return ask_popup.answer

    # show an mainpulatable overlap popup
    async def overlap(self, formation):
        overlap_popup = OverlapPopup(self, formation)
        overlap_popup.show()

        await overlap_popup.done_event.wait()

        overlap_popup.setParent(None)  # type:ignore


def bring_to_life():
    global window
    global event_loop
    global process_count
    global process_pool
    global communicator
    global app_close_event

    # ■■■■■ app ■■■■■

    app = QtWidgets.QApplication(sys.argv)

    # ■■■■■ theme ■■■■■

    # this part should be done after creating the app and before creating the window
    cwd = os.getcwd()
    QtGui.QFontDatabase.addApplicationFont(cwd + "/static/source_code_pro.ttf")
    QtGui.QFontDatabase.addApplicationFont(cwd + "/static/notosans_regular.ttf")
    QtGui.QFontDatabase.addApplicationFont(cwd + "/static/lexend_bold.ttf")
    default_font = QtGui.QFont("Noto Sans", 9)
    app.setFont(default_font)

    dark_palette = QtGui.QPalette()
    color_role = QtGui.QPalette.ColorRole
    dark_palette.setColor(color_role.Window, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(color_role.WindowText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.Base, QtGui.QColor(22, 22, 22))
    dark_palette.setColor(color_role.AlternateBase, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(color_role.ToolTipBase, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.ToolTipText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.Text, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.Button, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(color_role.ButtonText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.BrightText, QtGui.QColor(255, 180, 0))
    dark_palette.setColor(color_role.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(color_role.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(color_role.HighlightedText, QtGui.QColor(0, 0, 0))
    app.setStyle("Fusion")
    app.setPalette(dark_palette)

    # ■■■■■ prepare concurrency and parallelism ■■■■■

    process_count = multiprocessing.cpu_count()
    process_pool = ProcessPoolExecutor(process_count)
    communicator = multiprocessing.Manager()

    # ■■■■■ show and run ■■■■■

    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)
    app_close_event = asyncio.Event()

    window = Window()
    window.setPalette(dark_palette)
    window.show()

    async def keep_app_lifecycle():
        await app_close_event.wait()

    event_loop.create_task(window.boot())
    event_loop.run_until_complete(keep_app_lifecycle())
    event_loop.close()
