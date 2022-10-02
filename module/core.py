import sys
import threading
import time
import logging
import urllib
import math
import webbrowser
import os

from PySide6 import QtGui, QtWidgets, QtCore
import pyqtgraph
from apscheduler.schedulers.background import BlockingScheduler
import pandas as pd

from module import introduction
from module import process_toss
from module import thread_toss
from module.user_interface import Ui_MainWindow
from module.worker import manager
from module.worker import collector
from module.worker import transactor
from module.worker import simulator
from module.worker import strategist
from module.instrument.thread_pool_executor import ThreadPoolExecutor
from module.instrument.percent_axis_item import PercentAxisItem
from module.instrument.time_axis_item import TimeAxisItem
from module.instrument.telephone import Telephone
from module.instrument.api_streamer import ApiStreamer
from module.instrument.api_requester import ApiRequester
from module.instrument.log_handler import LogHandler
from module.recipe import outsource
from module.recipe import check_internet
from module.recipe import user_settings
from module.recipe import find_goodies
from module.recipe import examine_data_files
from module.widget.ask_popup import AskPopup
from module.widget.splash_screen import SplashScreen
from module.widget.symbol_box import SymbolBox
from module.widget.brand_label import BrandLabel
from module.widget.horizontal_divider import HorizontalDivider
from module.widget.overlap_popup import OverlapPopup
from module.shelf.token_selection import TokenSelection
from module.shelf.coin_selection import CoinSelection
from module.shelf.datapath_input import DatapathInput
from module.shelf.terms_of_agreement import TermsOfAgreement


class Window(QtWidgets.QMainWindow, Ui_MainWindow):
    def closeEvent(self, event):  # noqa:N802
        event.ignore()

        def job():
            if not self.should_finalize:
                self.closeEvent = lambda e: e.accept()
                self.undertake(self.close, True)

            if self.should_confirm_closing:
                question = [
                    "Really quit?",
                    "If Solsol is not turned on, data collection gets stopped as well."
                    " Solsol will proceed to finalizations such as closing network"
                    " connections and saving data.",
                    ["Cancel", "Shut down"],
                ]
                answer = self.ask(question)

                if answer in (0, 1):
                    return

            self.should_overlap_error = True

            AskPopup.done_event.set()
            OverlapPopup.done_event.set()

            total_steps = len(self.finalize_functions)
            done_steps = 0

            self.undertake(lambda: self.gauge.hide(), True)
            self.undertake(lambda: self.board.hide(), True)
            self.closeEvent = lambda e: e.ignore()

            splash_screen = None

            def job():
                nonlocal splash_screen
                splash_screen = SplashScreen()
                self.centralWidget().layout().addWidget(splash_screen)

            self.undertake(job, True)

            def job():
                while True:
                    if done_steps == total_steps:
                        time.sleep(1)
                        process_toss.terminate_pool()
                        self.closeEvent = lambda e: e.accept()
                        find_goodies.apply()
                        self.undertake(self.close, True)
                        break
                    else:
                        time.sleep(0.1)

            thread_toss.apply_async(job)

            self.scheduler.remove_all_jobs()
            self.scheduler.shutdown()
            ApiStreamer.close_all_forever()

            for finalize_function in self.finalize_functions:
                try:
                    finalize_function()
                except Exception:
                    pass
                done_steps += 1

        thread_toss.apply_async(job)

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # ■■■■■ basic sizing ■■■■■

        self.resize(0, 0)  # to smallest size possible
        self.splitter.setSizes([3, 1, 1, 2])
        self.splitter_2.setSizes([3, 1, 1, 2])

        # ■■■■■ app behavior settings ■■■■■

        self.should_finalize = False
        self.should_confirm_closing = True
        self.should_overlap_error = True

        # ■■■■■ hide the main widgets and go on to boot phase ■■■■■

        self.gauge.hide()
        self.board.hide()
        thread_toss.apply_async(self.boot)

    def boot(self):
        # ■■■■■ global settings of packages ■■■■■

        os.get_terminal_size = lambda *args: os.terminal_size((120, 90))
        pd.set_option("display.precision", 3)
        pd.set_option("display.min_rows", 20)
        pd.set_option("display.max_rows", 20)
        pyqtgraph.setConfigOptions(antialias=True)
        logging.getLogger().addHandler(LogHandler())

        # ■■■■■ guide frame ■■■■■

        splash_screen = None

        def job():
            nonlocal splash_screen
            splash_screen = SplashScreen()
            self.centralWidget().layout().addWidget(splash_screen)

        self.undertake(job, True)

        # ■■■■■ start basic things ■■■■■

        examine_data_files.do_first()
        user_settings.load()
        examine_data_files.do()
        user_settings.load()
        check_internet.start_monitoring()

        # ■■■■■ request internet connection ■■■■■

        while not check_internet.connected():
            question = [
                "No internet connection",
                "Internet connection is necessary for Solsol to start up.",
                ["Okay"],
            ]
            self.ask(question)
            time.sleep(1)

        # ■■■■■ check app settings ■■■■■

        if not user_settings.get_app_settings()["is_agreement_read"]:
            formation = [
                "Check terms of agreement",
                TermsOfAgreement,
                False,
                None,
            ]
            is_formed = self.overlap(formation)
            if not is_formed:
                return

        if user_settings.get_app_settings()["datapath"] is None:
            formation = [
                "Choose your data folder",
                DatapathInput,
                False,
                None,
            ]
            is_formed = self.overlap(formation)
            if not is_formed:
                return

        # ■■■■■ check data settings ■■■■■

        if user_settings.get_data_settings()["asset_token"] is None:
            formation = [
                "Choose a token to treat as your asset",
                TokenSelection,
                False,
                None,
            ]
            is_formed = self.overlap(formation)
            if not is_formed:
                return

        if user_settings.get_data_settings()["target_symbols"] is None:
            formation = [
                "Choose coins",
                CoinSelection,
                False,
                None,
            ]
            is_formed = self.overlap(formation)
            if not is_formed:
                return

        # ■■■■■ multiprocessing ■■■■■

        process_toss.start_pool()

        # ■■■■■ get information about target symbols ■■■■■

        asset_token = user_settings.get_data_settings()["asset_token"]
        target_symbols = user_settings.get_data_settings()["target_symbols"]
        response = ApiRequester().coinstats("GET", "/public/v1/coins")
        about_coins = response["coins"]

        coin_names = {}
        coin_icon_urls = {}
        coin_ranks = {}

        for about_coin in about_coins:
            coin_symbol = about_coin["symbol"]
            coin_names[coin_symbol] = about_coin["name"]
            coin_icon_urls[coin_symbol] = about_coin["icon"]
            coin_ranks[coin_symbol] = about_coin["rank"]

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
                image_data = urllib.request.urlopen(coin_icon_url).read()
                pixmap.loadFromData(image_data)
            else:
                pixmap.load("./static/icon/blank_coin.png")
            symbol_pixmaps[symbol] = pixmap

        token_icon_url = coin_icon_urls.get(asset_token, "")
        token_pixmap = QtGui.QPixmap()
        image_data = urllib.request.urlopen(token_icon_url).read()
        token_pixmap.loadFromData(image_data)

        def job():
            self.lineEdit.setText(user_settings.get_app_settings()["datapath"])

            icon_label = QtWidgets.QLabel(
                "",
                self,
                alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
            )
            icon_label.setPixmap(token_pixmap)
            icon_label.setScaledContents(True)
            icon_label.setFixedSize(30, 30)
            this_layout = QtWidgets.QHBoxLayout()
            self.verticalLayout_14.addLayout(this_layout)
            this_layout.addWidget(icon_label)
            text = asset_token
            token_font = QtGui.QFont()
            token_font.setPointSize(token_text_size)
            token_font.setWeight(QtGui.QFont.Weight.Bold)
            text_label = QtWidgets.QLabel(
                text,
                self,
                alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
            )
            text_label.setFont(token_font)
            self.verticalLayout_14.addWidget(text_label)
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
            self.price_labels = {}
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
                icon_label = QtWidgets.QLabel(
                    alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
                )
                this_layout = QtWidgets.QHBoxLayout()
                inside_layout.addLayout(this_layout)
                icon_label.setPixmap(symbol_pixmaps[symbol])
                icon_label.setScaledContents(True)
                icon_label.setFixedSize(50, 50)
                icon_label.setMargin(5)
                this_layout.addWidget(icon_label)
                name_label = QtWidgets.QLabel(
                    self.symbol_to_alias[symbol],
                    alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
                )
                name_font = QtGui.QFont()
                name_font.setPointSize(name_text_size)
                name_font.setWeight(QtGui.QFont.Weight.Bold)
                name_label.setFont(name_font)
                inside_layout.addWidget(name_label)
                price_label = QtWidgets.QLabel(
                    "",
                    alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
                )
                price_font = QtGui.QFont()
                price_font.setPointSize(price_text_size)
                price_font.setWeight(QtGui.QFont.Weight.Bold)
                price_label.setFont(price_font)
                inside_layout.addWidget(price_label)
                if coin_rank == 0:
                    text = coin_symbol
                else:
                    text = f"{coin_rank} - {coin_symbol}"
                detail_label = QtWidgets.QLabel(
                    text,
                    alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
                )
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

        self.undertake(job, True)

        # ■■■■■ show product icon and title ■■■■■

        def job():
            this_layout = self.horizontalLayout_13
            product_icon_pixmap = QtGui.QPixmap()
            with open("./static/product_icon_solsol.png", mode="rb") as file:
                product_icon_data = file.read()
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
            title_label = BrandLabel(self, "SOLSOL", 48)
            this_layout.addWidget(title_label)
            text = introduction.CURRENT_VERSION
            label = BrandLabel(self, text, 24)
            this_layout.addWidget(label)

        self.undertake(job, True)

        # ■■■■■ show package licenses ■■■■■

        def job():
            for category in ("CODE_SOURCES", "DEPENDENCIES"):
                if category == "CODE_SOURCES":
                    category_text = "Code sources"
                elif category == "DEPENDENCIES":
                    category_text = "Dependencies"
                category_label = QtWidgets.QLabel(category_text)
                self.verticalLayout_15.addWidget(category_label)
                divider = HorizontalDivider(self)
                self.verticalLayout_15.addWidget(divider)
                for dependency in getattr(introduction, category):
                    dependency_name = dependency[0]
                    dependency_version = dependency[1]
                    dependency_license = dependency[2]
                    dependency_url = dependency[3]

                    text = dependency_name
                    text += f" ({dependency_version})"
                    text += f" - {dependency_license}"

                    # card structure
                    card = QtWidgets.QGroupBox()
                    card.setFixedHeight(72)
                    card_layout = QtWidgets.QHBoxLayout(card)
                    license_label = QtWidgets.QLabel(
                        text,
                        alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
                    )
                    card_layout.addWidget(license_label)
                    spacer = QtWidgets.QSpacerItem(
                        0,
                        0,
                        QtWidgets.QSizePolicy.Policy.Expanding,
                        QtWidgets.QSizePolicy.Policy.Minimum,
                    )
                    card_layout.addItem(spacer)

                    def job(dependency_url=dependency_url):
                        webbrowser.open(dependency_url)

                    if dependency_url.startswith("http"):
                        text = dependency_url
                        link_button = QtWidgets.QPushButton(text, card)
                        outsource.do(link_button.clicked, job)
                        card_layout.addWidget(link_button)

                    self.verticalLayout_15.addWidget(card)

                spacer = QtWidgets.QSpacerItem(
                    0,
                    0,
                    QtWidgets.QSizePolicy.Policy.Minimum,
                    QtWidgets.QSizePolicy.Policy.Expanding,
                )
                self.verticalLayout_15.addItem(spacer)

        self.undertake(job, True)

        # ■■■■■ graph widgets ■■■■■

        def job():
            self.plot_widget = pyqtgraph.PlotWidget()
            self.plot_widget_1 = pyqtgraph.PlotWidget()
            self.plot_widget_4 = pyqtgraph.PlotWidget()
            self.plot_widget_6 = pyqtgraph.PlotWidget()
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

            plot_item = self.plot_widget.plotItem
            plot_item_1 = self.plot_widget_1.plotItem
            plot_item_4 = self.plot_widget_4.plotItem
            plot_item_6 = self.plot_widget_6.plotItem
            plot_item.vb.setLimits(xMin=0, yMin=0)
            plot_item_1.vb.setLimits(xMin=0, yMin=0)
            plot_item_4.vb.setLimits(xMin=0, yMin=0)
            plot_item_6.vb.setLimits(xMin=0)
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
            tick_font = QtGui.QFont("Consolas", 7)
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
                "price_indicators": [
                    plot_item.plot(connect="finite") for _ in range(20)
                ],
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

        self.undertake(job, True)

        def job():
            self.plot_widget_2 = pyqtgraph.PlotWidget()
            self.plot_widget_3 = pyqtgraph.PlotWidget()
            self.plot_widget_5 = pyqtgraph.PlotWidget()
            self.plot_widget_7 = pyqtgraph.PlotWidget()
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
            plot_item_2.vb.setLimits(xMin=0, yMin=0)
            plot_item_3.vb.setLimits(xMin=0, yMin=0)
            plot_item_5.vb.setLimits(xMin=0, yMin=0)
            plot_item_7.vb.setLimits(xMin=0)
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
            tick_font = QtGui.QFont("Consolas", 7)
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
                "price_indicators": [
                    plot_item_2.plot(connect="finite") for _ in range(20)
                ],
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

        self.undertake(job, True)

        # ■■■■■ prepare auto executions ■■■■■

        self.scheduler = BlockingScheduler(timezone="UTC")
        self.scheduler.add_executor(ThreadPoolExecutor(), "thread_pool_executor")

        # ■■■■■ workers ■■■■■

        collector.bring_to_life()
        transactor.bring_to_life()
        simulator.bring_to_life()
        strategist.bring_to_life()
        manager.bring_to_life()

        # ■■■■■ initialize functions ■■■■■

        self.initialize_functions = []
        self.initialize_functions.append(
            lambda: collector.me.get_exchange_information(),
        )
        self.initialize_functions.append(
            lambda: strategist.me.display_strategies(),
        )
        self.initialize_functions.append(
            lambda: transactor.me.display_strategy_index(),
        )
        self.initialize_functions.append(
            lambda: transactor.me.watch_binance(),
        )
        self.initialize_functions.append(
            lambda: transactor.me.update_user_data_stream(),
        )
        self.initialize_functions.append(
            lambda: transactor.me.display_lines(),
        )
        self.initialize_functions.append(
            lambda: transactor.me.display_day_range(),
        )
        self.initialize_functions.append(
            lambda: simulator.me.display_lines(),
        )
        self.initialize_functions.append(
            lambda: simulator.me.display_year_range(),
        )
        self.initialize_functions.append(
            lambda: manager.me.check_binance_limits(),
        )
        self.initialize_functions.append(
            lambda: transactor.me.pay_fees(),
        )
        self.initialize_functions.append(
            lambda: transactor.me.update_discount_rate(),
        )

        # ■■■■■ finalize functions ■■■■■

        self.finalize_functions = []

        self.finalize_functions.append(
            lambda: transactor.me.save_large_files(),
        )
        self.finalize_functions.append(
            lambda: transactor.me.save_scribbles(),
        )
        self.finalize_functions.append(
            lambda: strategist.me.save_strategies(),
        )
        self.finalize_functions.append(
            lambda: collector.me.save_candle_data(),
        )

        # ■■■■■ change logging settings ■■■■■

        self.should_overlap_error = False
        logger = logging.getLogger("solsol")
        logger.setLevel("DEBUG")
        logger.info("Started up")

        # ■■■■■ connect events to functions ■■■■■

        def job():
            # gauge
            job = manager.me.toggle_board_availability
            outsource.do(self.gauge.clicked, job)

            # special widgets
            job = transactor.me.display_range_information
            outsource.do(self.plot_widget.sigRangeChanged, job)
            job = transactor.me.set_minimum_view_range
            outsource.do(self.plot_widget.sigRangeChanged, job)
            job = simulator.me.display_range_information
            outsource.do(self.plot_widget_2.sigRangeChanged, job)
            job = simulator.me.set_minimum_view_range
            outsource.do(self.plot_widget_2.sigRangeChanged, job)

            # normal widgets
            job = simulator.me.update_calculation_settings
            outsource.do(self.comboBox.currentIndexChanged, job)
            job = transactor.me.update_automation_settings
            outsource.do(self.comboBox_2.currentIndexChanged, job)
            job = transactor.me.update_automation_settings
            outsource.do(self.checkBox.toggled, job)
            job = simulator.me.calculate
            outsource.do(self.pushButton_3.clicked, job)
            job = manager.me.open_datapath
            outsource.do(self.pushButton_8.clicked, job)
            job = simulator.me.update_presentation_settings
            outsource.do(self.spinBox_2.editingFinished, job)
            job = simulator.me.update_presentation_settings
            outsource.do(self.doubleSpinBox.editingFinished, job)
            job = simulator.me.update_presentation_settings
            outsource.do(self.doubleSpinBox_2.editingFinished, job)
            job = simulator.me.erase
            outsource.do(self.pushButton_4.clicked, job)
            job = simulator.me.update_calculation_settings
            outsource.do(self.comboBox_5.currentIndexChanged, job)
            job = transactor.me.update_keys
            outsource.do(self.lineEdit_4.editingFinished, job)
            job = transactor.me.update_keys
            outsource.do(self.lineEdit_6.editingFinished, job)
            job = manager.me.run_script
            outsource.do(self.pushButton.clicked, job)
            job = transactor.me.toggle_frequent_draw
            outsource.do(self.checkBox_2.toggled, job)
            job = simulator.me.toggle_combined_draw
            outsource.do(self.checkBox_3.toggled, job)
            job = transactor.me.display_day_range
            outsource.do(self.pushButton_14.clicked, job)
            job = simulator.me.display_year_range
            outsource.do(self.pushButton_15.clicked, job)
            job = simulator.me.delete_calculation_data
            outsource.do(self.pushButton_16.clicked, job)
            job = simulator.me.draw
            outsource.do(self.pushButton_17.clicked, job)
            job = collector.me.download_fill_candle_data
            outsource.do(self.pushButton_2.clicked, job)
            job = transactor.me.update_mode_settings
            outsource.do(self.spinBox.editingFinished, job)
            job = manager.me.deselect_log_output
            outsource.do(self.pushButton_6.clicked, job)
            job = manager.me.reset_datapath
            outsource.do(self.pushButton_22.clicked, job)
            job = transactor.me.update_viewing_symbol
            outsource.do(self.comboBox_4.currentIndexChanged, job)
            job = simulator.me.update_viewing_symbol
            outsource.do(self.comboBox_6.currentIndexChanged, job)
            job = manager.me.open_documentation
            outsource.do(self.pushButton_7.clicked, job)
            job = strategist.me.add_blank_strategy
            outsource.do(self.pushButton_5.clicked, job)
            job = transactor.me.show_fees_and_revenues
            outsource.do(self.pushButton_9.clicked, job)

        self.undertake(job, True)

        # ■■■■■ submenu actions ■■■■■

        def job():
            action_menu = QtWidgets.QMenu(self)
            self.pushButton_13.setMenu(action_menu)
            text = "Save candle data"
            job = collector.me.save_candle_data
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Save every year's candle data"
            job = collector.me.save_all_years_history
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Open binance historical data webpage"
            job = collector.me.open_binance_data_page
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Stop filling candle data"
            job = collector.me.stop_filling_candle_data
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)

            action_menu = QtWidgets.QMenu(self)
            self.pushButton_12.setMenu(action_menu)
            text = "Open binance exchange"
            job = transactor.me.open_exchange
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            self.pushButton_12.setMenu(action_menu)
            text = "Open binance testnet exchange"
            job = transactor.me.open_testnet_exchange
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Open binance wallet"
            job = transactor.me.open_futures_wallet_page
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Open binance API management webpage"
            job = transactor.me.open_api_management_page
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Cancel all open orders on this symbol"
            job = transactor.me.cancel_symbol_orders
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Display same range as simulation graph"
            job = transactor.me.match_graph_range
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Change fee settings"
            job = transactor.me.update_fee_settings
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Show Raw Account State Object"
            job = transactor.me.show_raw_account_state_object
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)

            action_menu = QtWidgets.QMenu(self)
            self.pushButton_11.setMenu(action_menu)
            text = "Calculate temporarily only on visible range"
            job = simulator.me.simulate_only_visible
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Stop calculation"
            job = simulator.me.stop_calculation
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Find spots with lowest unrealized profit"
            job = simulator.me.analyze_unrealized_peaks
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Display same range as transaction graph"
            job = simulator.me.match_graph_range
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)

            action_menu = QtWidgets.QMenu(self)
            self.pushButton_10.setMenu(action_menu)
            text = "Make a small error on purpose"
            job = manager.me.make_small_exception
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Show test popup"
            job = manager.me.open_sample_ask_popup
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)
            text = "Match system time with binance server"
            job = manager.me.match_system_time
            new_action = action_menu.addAction(text)
            outsource.do(new_action.triggered, job)

        self.undertake(job, True)

        # ■■■■■ initialize functions ■■■■■

        def job(function):
            function()

        for initialize_function in self.initialize_functions:
            try:
                initialize_function()
            except Exception:
                pass

        # ■■■■■ start repetitive timer ■■■■■

        thread_toss.apply_async(lambda: self.scheduler.start())

        # ■■■■■ activate finalization ■■■■■

        self.should_finalize = True

        # ■■■■■ wait until the contents are filled ■■■■■

        time.sleep(1)

        # ■■■■■ show main widgets ■■■■■

        self.undertake(lambda: splash_screen.setParent(None), True)
        self.undertake(lambda: self.board.show(), True)
        self.undertake(lambda: self.gauge.show(), True)

    # takes function and run it on the main thread
    def undertake(self, job, wait_return, called_remotely=False, holder=None):
        if not called_remotely:
            holder = [threading.Event(), None]
            telephone = Telephone()
            telephone.signal.connect(self.undertake)
            telephone.signal.emit(job, False, True, holder)
            if wait_return:
                holder[0].wait()
                return holder[1]

        else:
            try:
                returned = job()
                holder[1] = returned
            except Exception:
                logger = logging.getLogger("solsol")
                logger.exception("Exception occured from the main thread")
            holder[0].set()

    # show an ask popup and blocks the stack
    def ask(self, question):
        ask_popup = None

        def job():
            nonlocal ask_popup
            ask_popup = AskPopup(self, question)
            ask_popup.show()

        self.undertake(job, True)

        if ask_popup is None:
            return 0

        ask_popup.done_event.wait()

        def job():
            ask_popup.setParent(None)

        self.undertake(job, False)

        return ask_popup.answer

    # show an mainpulatable overlap popup
    def overlap(self, formation):
        overlap_popup = None

        def job():
            nonlocal overlap_popup
            overlap_popup = OverlapPopup(self, formation)
            overlap_popup.show()

        self.undertake(job, True)

        if overlap_popup is None:
            return False

        overlap_popup.done_event.wait()

        def job():
            overlap_popup.setParent(None)

        self.undertake(job, False)

        return True


window = None


def bring_to_life():
    global window

    # ■■■■■ app ■■■■■

    app = QtWidgets.QApplication(sys.argv)

    # ■■■■■ theme ■■■■■

    # this part should be done after creating the app and before creating the window
    QtGui.QFontDatabase.addApplicationFont("./static/consolas.ttf")
    QtGui.QFontDatabase.addApplicationFont("./static/notosans_regular.ttf")
    QtGui.QFontDatabase.addApplicationFont("./static/lexend_bold.ttf")
    default_font = QtGui.QFont("Noto Sans", 9)
    app.setFont(default_font)

    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(22, 22, 22))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(QtGui.QPalette.Text, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 180, 0))
    dark_palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(0, 0, 0))
    app.setStyle("Fusion")
    app.setPalette(dark_palette)

    # ■■■■■ window ■■■■■

    window = Window()
    window.setPalette(dark_palette)

    # ■■■■■ show ■■■■■

    window.show()
    sys.exit(getattr(app, "exec")())
