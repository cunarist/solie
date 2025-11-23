import math
import os
from asyncio import Event, sleep
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from typing import Any, NamedTuple, override

import aiofiles
import aiofiles.os
import pandas as pd
import pyqtgraph
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QFont, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)

from solie.common import PACKAGE_PATH, PACKAGE_VERSION, spawn
from solie.overlay import CoinSelection, DatapathInput, TokenSelection
from solie.utility import (
    LONG_SYMBOL_LIST_THRESHOLD,
    ApiRequester,
    DataSettings,
    LogHandler,
    SolieConfig,
    internet_connected,
    read_data_settings,
    read_datapath,
    save_data_settings,
    save_datapath,
    start_monitoring_internet,
)
from solie.widget import (
    AskPopup,
    BrandLabel,
    GraphLines,
    HorizontalDivider,
    SplashScreen,
    SymbolBox,
    ask,
    overlay,
)

from .compiled import Ui_MainWindow

logger = getLogger(__name__)


class SymbolBoxParams(NamedTuple):
    """Parameters for populating a symbol box."""

    symbol: str
    pixmap: QPixmap
    coin_symbol: str
    coin_rank: int
    name_text_size: int
    price_text_size: int
    detail_text_size: int


class Window(QMainWindow, Ui_MainWindow):
    def __init__(self, close_event: Event, config: SolieConfig) -> None:
        super().__init__()

        self._close_event = close_event
        self.config = config

        self.datapath: Path
        self.data_settings: DataSettings

        self.last_interaction = datetime.now(timezone.utc)
        self._splash_screen: SplashScreen
        self.price_labels: dict[str, QLabel] = {}

        self.should_confirm_closing = False

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()

        async def job_close() -> None:
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

            self.gauge.hide()
            self.board.hide()
            self.closeEvent = lambda event: event.ignore()

            self._splash_screen.show()
            self._close_event.set()

        spawn(job_close())

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.last_interaction = datetime.now(timezone.utc)

        if self.board.isEnabled():
            return

        async def job_ask() -> None:
            answer = await ask(
                "Board is locked. Do you want to unlock it?",
                "You will be able to manipulate the board again.",
                ["No", "Yes"],
            )
            if answer in (0, 1):
                return
            self.board.setEnabled(True)

        spawn(job_ask())

    async def boot(self) -> None:
        """Initialize and boot the application window."""
        self._setup_ui()
        await self._setup_splash_screen()
        self._configure_global_settings()
        await self._set_window_icon()
        await self._ensure_internet_connection()
        await self._load_or_create_datapath()
        await self._load_or_create_data_settings()

        asset_token = self.data_settings.asset_token
        target_symbols = self.data_settings.target_symbols

        coin_info = await self._fetch_coin_information()
        self._create_symbol_aliases(asset_token, target_symbols, coin_info)

        await self._setup_ui_widgets(asset_token, target_symbols, coin_info)
        await self._setup_graphs()
        await self._setup_logging()

    def _setup_ui(self) -> None:
        """Setup basic UI elements and sizes."""
        self.setupUi(self)
        self.setMouseTracking(True)
        self.resize(0, 0)  # To smallest size possible
        self.splitter.setSizes([3, 1, 1, 2])
        self.splitter_2.setSizes([3, 1, 1, 2])

    async def _setup_splash_screen(self) -> None:
        """Initialize and display the splash screen."""
        self.gauge.hide()
        self.board.hide()
        self._splash_screen = SplashScreen()
        central_layout = self.centralWidget().layout()
        if central_layout is None:
            raise ValueError("There's no central layout")
        central_layout.addWidget(self._splash_screen)
        self.show()

    def _configure_global_settings(self) -> None:
        """Configure global settings for libraries."""
        os.get_terminal_size = lambda *args: os.terminal_size((150, 90))
        pd.set_option("display.precision", 6)
        pd.set_option("display.min_rows", 100)
        pd.set_option("display.max_rows", 100)
        pyqtgraph.setConfigOptions(antialias=True)

    async def _set_window_icon(self) -> None:
        """Load and set the window icon."""
        filepath = PACKAGE_PATH / "static" / "product_icon.png"
        async with aiofiles.open(filepath, mode="rb") as file:
            product_icon_data = await file.read()
        product_icon_pixmap = QPixmap()
        product_icon_pixmap.loadFromData(product_icon_data)
        self.setWindowIcon(product_icon_pixmap)

    async def _ensure_internet_connection(self) -> None:
        """Wait for internet connection to be established."""
        await start_monitoring_internet()
        while not internet_connected():
            await ask(
                "No internet connection",
                "Internet connection is necessary for Solie to start up.",
                ["Retry"],
            )
            await sleep(1.0)

    async def _load_or_create_datapath(self) -> None:
        """Load existing datapath or prompt user to create one."""
        datapath = await read_datapath()
        if not datapath:
            datapath = await overlay(DatapathInput())
            await save_datapath(datapath)
        self.datapath = datapath

    async def _load_or_create_data_settings(self) -> None:
        """Load existing data settings or prompt user to create them."""
        data_settings = await read_data_settings(self.datapath)
        if not data_settings:
            asset_token = await overlay(TokenSelection())
            target_symbols = await overlay(CoinSelection(asset_token))
            data_settings = DataSettings(
                asset_token=asset_token,
                target_symbols=target_symbols,
            )
            await save_data_settings(data_settings, self.datapath)
        self.data_settings = data_settings

    async def _fetch_coin_information(self) -> dict[str, dict[str, Any]]:
        """Fetch coin information from CoinGecko API."""
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
            raw_symbol: str = about_coin["symbol"]
            coin_symbol = raw_symbol.upper()
            coin_names[coin_symbol] = about_coin["name"]
            coin_icon_urls[coin_symbol] = about_coin["image"]
            coin_ranks[coin_symbol] = about_coin["market_cap_rank"]

        return {"names": coin_names, "urls": coin_icon_urls, "ranks": coin_ranks}

    def _create_symbol_aliases(
        self,
        asset_token: str,
        target_symbols: list[str],
        coin_info: dict[str, dict[str, Any]],
    ) -> None:
        """Create mapping between symbols and their aliases."""
        coin_names = coin_info["names"]

        self.alias_to_symbol: dict[str, str] = {}
        self.symbol_to_alias: dict[str, str] = {}

        for symbol in target_symbols:
            coin_symbol = symbol.removesuffix(asset_token)
            coin_name = coin_names.get(coin_symbol, "")
            alias = coin_name if coin_name else coin_symbol
            self.alias_to_symbol[alias] = symbol
            self.symbol_to_alias[symbol] = alias

    async def _setup_ui_widgets(
        self,
        asset_token: str,
        target_symbols: list[str],
        coin_info: dict[str, dict[str, Any]],
    ) -> None:
        """Setup all UI widgets based on data settings."""
        coin_icon_urls = coin_info["urls"]
        coin_ranks = coin_info["ranks"]

        api_requester = ApiRequester()

        # Load symbol pixmaps
        symbol_pixmaps: dict[str, QPixmap] = {}
        for symbol in target_symbols:
            coin_symbol = symbol.removesuffix(asset_token)
            coin_icon_url = coin_icon_urls.get(coin_symbol, "")
            pixmap = QPixmap()
            if coin_icon_url:
                image_data = await api_requester.bytes(coin_icon_url)
                pixmap.loadFromData(image_data)
            else:
                pixmap.load(str(PACKAGE_PATH / "static" / "icon" / "blank_coin.png"))
            symbol_pixmaps[symbol] = pixmap

        # Load token pixmap
        token_icon_url = coin_icon_urls.get(asset_token, "")
        token_pixmap = QPixmap()
        if token_icon_url:
            image_data = await api_requester.bytes(token_icon_url)
            token_pixmap.loadFromData(image_data)

        # Setup datapath display
        text = str(self.datapath)
        self.lineEdit.setText(text)
        self.lineEdit.setCursorPosition(len(text))

        # Setup token display
        self._setup_token_display(asset_token, token_pixmap)

        # Setup combo boxes
        self._setup_combo_boxes(target_symbols, symbol_pixmaps)

        # Setup symbol boxes
        self._setup_symbol_boxes(
            asset_token, target_symbols, symbol_pixmaps, coin_ranks
        )

        # Setup product branding
        await self._setup_product_branding()

    def _setup_token_display(self, asset_token: str, token_pixmap: QPixmap) -> None:
        """Setup the token display area."""
        token_text_size = 14

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(token_pixmap)
        icon_label.setScaledContents(True)
        icon_label.setFixedSize(30, 30)
        this_layout = QHBoxLayout()
        self.verticalLayout_14.addLayout(this_layout)
        this_layout.addWidget(icon_label)

        token_font = QFont()
        token_font.setPointSize(token_text_size)
        token_font.setWeight(QFont.Weight.Bold)
        token_label = QLabel()
        token_label.setText(asset_token)
        token_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        token_label.setFont(token_font)
        self.verticalLayout_14.addWidget(token_label)

        # Add spacing
        for point_size in [1, 2]:
            spacing_text = QLabel("")
            spacing_text_font = QFont()
            spacing_text_font.setPointSize(point_size)
            spacing_text.setFont(spacing_text_font)
            if point_size == 1:
                self.verticalLayout_14.addWidget(spacing_text)
            else:
                this_layout = QHBoxLayout()
                self.verticalLayout_14.addLayout(this_layout)
                divider = HorizontalDivider(self)
                divider.setFixedWidth(320)
                this_layout.addWidget(divider)
                self.verticalLayout_14.addWidget(spacing_text)

    def _setup_combo_boxes(
        self, target_symbols: list[str], symbol_pixmaps: dict[str, QPixmap]
    ) -> None:
        """Setup combo boxes with symbol icons."""
        for symbol in target_symbols:
            icon = QIcon()
            icon.addPixmap(symbol_pixmaps[symbol])
            alias = self.symbol_to_alias[symbol]
            self.comboBox_4.addItem(icon, alias)
            self.comboBox_6.addItem(icon, alias)

    def _setup_symbol_boxes(
        self,
        asset_token: str,
        target_symbols: list[str],
        symbol_pixmaps: dict[str, QPixmap],
        coin_ranks: dict[str, int],
    ) -> None:
        """Setup symbol boxes for each trading symbol."""
        name_text_size = 11
        price_text_size = 9
        detail_text_size = 7

        is_long = len(target_symbols) > LONG_SYMBOL_LIST_THRESHOLD

        # Add spacers
        for layout in [self.horizontalLayout_20, self.horizontalLayout_17]:
            spacer = QSpacerItem(
                0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
            layout.addItem(spacer)

        for turn, symbol in enumerate(target_symbols):
            coin_symbol = symbol.removesuffix(asset_token)
            coin_rank = coin_ranks.get(coin_symbol, 0)
            symbol_box = SymbolBox()

            # Choose layout based on symbol count
            if is_long and turn + 1 > math.floor(len(target_symbols) / 2):
                self.horizontalLayout_17.addWidget(symbol_box)
            else:
                self.horizontalLayout_20.addWidget(symbol_box)

            self._populate_symbol_box(
                symbol_box,
                SymbolBoxParams(
                    symbol=symbol,
                    pixmap=symbol_pixmaps[symbol],
                    coin_symbol=coin_symbol,
                    coin_rank=coin_rank,
                    name_text_size=name_text_size,
                    price_text_size=price_text_size,
                    detail_text_size=detail_text_size,
                ),
            )

        # Add trailing spacers
        for layout in [self.horizontalLayout_20, self.horizontalLayout_17]:
            spacer = QSpacerItem(
                0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
            layout.addItem(spacer)

    def _populate_symbol_box(
        self,
        symbol_box: SymbolBox,
        params: SymbolBoxParams,
    ) -> None:
        """Populate a symbol box with icon, name, price, and details."""
        inside_layout = QVBoxLayout(symbol_box)

        # Top spacer
        spacer = QSpacerItem(
            0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        inside_layout.addItem(spacer)

        # Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        this_layout = QHBoxLayout()
        inside_layout.addLayout(this_layout)
        icon_label.setPixmap(params.pixmap)
        icon_label.setScaledContents(True)
        icon_label.setFixedSize(50, 50)
        icon_label.setMargin(5)
        this_layout.addWidget(icon_label)

        # Name
        name_label = QLabel()
        name_label.setText(self.symbol_to_alias[params.symbol])
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(params.name_text_size)
        name_font.setWeight(QFont.Weight.Bold)
        name_label.setFont(name_font)
        inside_layout.addWidget(name_label)

        # Price
        price_label = QLabel()
        price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        price_font = QFont()
        price_font.setPointSize(params.price_text_size)
        price_font.setWeight(QFont.Weight.Bold)
        price_label.setFont(price_font)
        inside_layout.addWidget(price_label)

        # Details
        text = (
            params.coin_symbol
            if params.coin_rank == 0
            else f"{params.coin_rank} - {params.coin_symbol}"
        )
        detail_label = QLabel()
        detail_label.setText(text)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_font = QFont()
        detail_font.setPointSize(params.detail_text_size)
        detail_font.setWeight(QFont.Weight.Bold)
        detail_label.setFont(detail_font)
        inside_layout.addWidget(detail_label)

        self.price_labels[params.symbol] = price_label

        # Bottom spacer
        spacer = QSpacerItem(
            0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        inside_layout.addItem(spacer)

    async def _setup_product_branding(self) -> None:
        """Setup product icon and title."""
        this_layout = self.horizontalLayout_13

        # Product icon
        product_icon_pixmap = QPixmap()
        filepath = PACKAGE_PATH / "static" / "product_icon.png"
        async with aiofiles.open(filepath, mode="rb") as file:
            product_icon_data = await file.read()
        product_icon_pixmap.loadFromData(product_icon_data)
        product_icon_label = QLabel("", self)
        product_icon_label.setPixmap(product_icon_pixmap)
        product_icon_label.setScaledContents(True)
        product_icon_label.setFixedSize(80, 80)
        this_layout.addWidget(product_icon_label)

        # Spacing
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(8)
        spacing_text.setFont(spacing_text_font)
        this_layout.addWidget(spacing_text)

        # Title
        title_label = BrandLabel(self, "SOLIE", 48)
        this_layout.addWidget(title_label)

        # Version
        label = BrandLabel(self, PACKAGE_VERSION, 24)
        this_layout.addWidget(label)

    async def _setup_graphs(self) -> None:
        """Setup transaction and simulation graph widgets."""
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

    async def _setup_logging(self) -> None:
        """Setup logging system."""

        def log_callback(summarization: str, log_content: str) -> None:
            self.listWidget.add_item(summarization, log_content)

        log_path = self.datapath / "+logs"
        await aiofiles.os.makedirs(log_path, exist_ok=True)
        log_handler = LogHandler(log_path, log_callback)
        getLogger().addHandler(log_handler)

    def reveal(self) -> None:
        self.should_confirm_closing = True

        self._splash_screen.hide()
        self.board.show()
        self.gauge.show()
