import logging
import math
import os
from asyncio import Event, sleep
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
import aiofiles.os
import pandas as pd
import pyqtgraph
from PySide6 import QtCore, QtGui, QtWidgets
from typing_extensions import override

from solie.common import PACKAGE_PATH, PACKAGE_VERSION, spawn
from solie.overlay import CoinSelection, DatapathInput, TokenSelection
from solie.utility import (
    ApiRequester,
    DataSettings,
    LogHandler,
    SolieConfig,
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
    GraphLines,
    HorizontalDivider,
    SplashScreen,
    SymbolBox,
    ask,
    overlay,
)

from .compiled import Ui_MainWindow

logger = logging.getLogger(__name__)


class Window(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, close_event: Event, config: SolieConfig):
        super().__init__()

        self.close_event = close_event
        self.config = config

        self.datapath: Path
        self.data_settings: DataSettings

        self.last_interaction = datetime.now(timezone.utc)
        self.splash_screen: SplashScreen
        self.price_labels: dict[str, QtWidgets.QLabel] = {}

        self.should_confirm_closing = False

    @override
    def closeEvent(self, event):
        event.ignore()

        async def job_close():
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

            self.splash_screen.show()
            self.close_event.set()

        spawn(job_close())

    @override
    def mouseReleaseEvent(self, event):
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

        spawn(job_ask())

    async def boot(self):
        # ■■■■■ Do basic Qt things ■■■■■

        self.setupUi(self)
        self.setMouseTracking(True)

        # ■■■■■ Basic sizing ■■■■■

        self.resize(0, 0)  # To smallest size possible
        self.splitter.setSizes([3, 1, 1, 2])
        self.splitter_2.setSizes([3, 1, 1, 2])

        # ■■■■■ Show the splash screen ■■■■■

        self.gauge.hide()
        self.board.hide()
        self.splash_screen = SplashScreen()
        central_layout = self.centralWidget().layout()
        if central_layout is None:
            raise ValueError("There's no central layout")
        central_layout.addWidget(self.splash_screen)

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

        # ■■■■■ Request internet connection ■■■■■

        spawn(monitor_internet())
        await is_internet_checked.wait()
        while not internet_connected():
            await ask(
                "No internet connection",
                "Internet connection is necessary for Solie to start up.",
                ["Retry"],
            )
            await sleep(1.0)

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

        # ■■■■■ Get information about target symbols ■■■■■

        api_requester = ApiRequester()
        response = await api_requester.coingecko(
            "GET",
            "/api/v3/coins/markets",
            {
                "vs_currency": "usd",
            },
        )

        coin_names: dict[str, str] = {}
        coin_icon_urls: dict[str, str] = {}
        coin_ranks: dict[str, int] = {}

        for about_coin in response:
            coin_symbol = about_coin["symbol"].upper()
            coin_names[coin_symbol] = about_coin["name"]
            coin_icon_urls[coin_symbol] = about_coin["image"]
            coin_ranks[coin_symbol] = about_coin["market_cap_rank"]

        self.alias_to_symbol: dict[str, str] = {}
        self.symbol_to_alias: dict[str, str] = {}

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

        # ■■■■■ Graph widgets ■■■■■

        graph_lines = GraphLines()
        self.horizontalLayout_7.addWidget(graph_lines.price_widget)
        self.horizontalLayout_16.addWidget(graph_lines.volume_widget)
        self.horizontalLayout_28.addWidget(graph_lines.abstract_widget)
        self.horizontalLayout_29.addWidget(graph_lines.asset_widget)
        self.transaction_graph = graph_lines

        graph_lines = GraphLines()
        self.horizontalLayout.addWidget(graph_lines.price_widget)
        self.horizontalLayout_19.addWidget(graph_lines.volume_widget)
        self.horizontalLayout_31.addWidget(graph_lines.abstract_widget)
        self.horizontalLayout_30.addWidget(graph_lines.asset_widget)
        self.simulation_graph = graph_lines

        # ■■■■■ Prepare logging ■■■■■

        def log_callback(summarization: str, log_content: str):
            self.listWidget.add_item(summarization, log_content)

        log_path = datapath / "+logs"
        await aiofiles.os.makedirs(log_path, exist_ok=True)
        log_handler = LogHandler(log_path, log_callback)
        logging.root.addHandler(log_handler)

    def reveal(self):
        self.should_confirm_closing = True

        self.splash_screen.hide()
        self.board.show()
        self.gauge.show()
