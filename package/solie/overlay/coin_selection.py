"""Coin selection overlay for choosing trading pairs."""

from asyncio import Event
from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from solie.common import PACKAGE_PATH, outsource, spawn
from solie.utility import MAX_SELECTED_COINS, MIN_SELECTED_COINS, ApiRequester
from solie.widget import HorizontalDivider, ask


class CoinMetadata(NamedTuple):
    """Metadata for coins including names, icons, and rankings."""

    coin_names: dict[str, str]
    coin_icon_urls: dict[str, str]
    coin_ranks: dict[str, int]


class CoinSelection:
    """Overlay for selecting coins to trade."""

    title = "Choose coins to observe and trade"
    close_button = False
    done_event = Event()

    def __init__(self, asset_token: str) -> None:
        """Initialize coin selection overlay."""
        super().__init__()
        self.widget = QWidget()
        self.result: list[str]

        self.is_closed = False
        self.asset_token = asset_token
        spawn(self.fill())

    async def confirm_closing(self) -> bool:
        """Confirm if overlay can be closed."""
        return True

    async def fill(self) -> None:
        """Fill the coin selection UI with available coins."""
        api_requester = ApiRequester()

        # Fetch and process data
        available_symbols = await self._fetch_available_symbols(api_requester)
        coin_metadata = await self._fetch_coin_metadata(api_requester)
        sorted_symbols = self._sort_by_market_cap(available_symbols, coin_metadata)

        # Build UI
        symbol_icon_labels = self._build_ui(sorted_symbols, coin_metadata)

        # Load icons asynchronously
        self._load_coin_icons_async(
            api_requester,
            symbol_icon_labels,
            coin_metadata.coin_icon_urls,
        )

    async def _fetch_available_symbols(self, api_requester: ApiRequester) -> list[str]:
        """Fetch available trading symbols from Binance."""
        available_symbols: list[str] = []

        response = await api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload={},
        )
        about_symbols = response["symbols"]
        for about_symbol in about_symbols:
            symbol: str = about_symbol["symbol"]
            if symbol.endswith(self.asset_token):
                available_symbols.append(symbol)

        return available_symbols

    async def _fetch_coin_metadata(self, api_requester: ApiRequester) -> CoinMetadata:
        """Fetch coin metadata from CoinGecko."""
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

        return CoinMetadata(
            coin_names=coin_names,
            coin_icon_urls=coin_icon_urls,
            coin_ranks=coin_ranks,
        )

    def _sort_by_market_cap(
        self,
        available_symbols: list[str],
        coin_metadata: CoinMetadata,
    ) -> list[str]:
        """Sort symbols by market cap rank (highest rank first)."""
        coin_ranks = coin_metadata.coin_ranks

        for rank in range(250, 0, -1):
            if rank not in coin_ranks.values():
                continue
            index_to_find = list(coin_ranks.values()).index(rank)
            coin_symbol = list(coin_ranks.keys())[index_to_find]
            symbol = coin_symbol + self.asset_token
            if symbol not in available_symbols:
                continue
            original_index = available_symbols.index(symbol)
            available_symbols.insert(0, available_symbols.pop(original_index))

        return available_symbols

    def _build_ui(
        self,
        sorted_symbols: list[str],
        coin_metadata: CoinMetadata,
    ) -> dict[str, QLabel]:
        """Build the main UI layout."""
        symbol_checkboxes: dict[str, QCheckBox] = {}
        symbol_icon_labels: dict[str, QLabel] = {}

        full_layout = QHBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # Top spacer
        self._add_spacer(cards_layout, vertical=True)

        # Build coin selection card
        self._build_coin_selection_card(
            cards_layout,
            sorted_symbols,
            coin_metadata,
            symbol_checkboxes,
            symbol_icon_labels,
        )

        # Build confirmation card
        self._build_confirmation_card(cards_layout, symbol_checkboxes)

        # Bottom spacer
        self._add_spacer(cards_layout, vertical=True)

        return symbol_icon_labels

    def _add_spacer(self, layout: QVBoxLayout, vertical: bool = False) -> None:
        """Add a spacer to the layout."""
        if vertical:
            spacer = QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        else:
            spacer = QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        layout.addItem(spacer)

    def _build_coin_selection_card(
        self,
        cards_layout: QVBoxLayout,
        sorted_symbols: list[str],
        coin_metadata: CoinMetadata,
        symbol_checkboxes: dict[str, QCheckBox],
        symbol_icon_labels: dict[str, QLabel],
    ) -> None:
        """Build the card with coin checkboxes."""
        coin_names = coin_metadata.coin_names
        coin_ranks = coin_metadata.coin_ranks

        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        detail_text = QLabel()
        detail_text.setText(
            "These are all the available coins from the token you chose."
            "\nYou can select a minimum of 1 and a maximum of 12.",
        )
        detail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        self._add_small_spacing(card_layout)

        divider = HorizontalDivider(self.widget)
        card_layout.addWidget(divider)

        self._add_small_spacing(card_layout)

        input_layout = QGridLayout()
        blank_coin_pixmap = QPixmap()
        blank_coin_pixmap.load(str(PACKAGE_PATH / "static" / "icon" / "blank_coin.png"))

        for turn, symbol in enumerate(sorted_symbols):
            coin_symbol = symbol.removesuffix(self.asset_token)
            coin_name = coin_names.get(coin_symbol, "")
            coin_rank = coin_ranks.get(coin_symbol, 0)

            this_layout = QHBoxLayout()
            row = turn // 2
            column = turn % 2
            input_layout.addLayout(this_layout, row, column)

            checkbox = QCheckBox(card)
            symbol_checkboxes[symbol] = checkbox
            this_layout.addWidget(checkbox)

            icon_label = QLabel("", card)
            icon_label.setPixmap(blank_coin_pixmap)
            icon_label.setScaledContents(True)
            icon_label.setFixedSize(40, 40)
            icon_label.setMargin(5)
            this_layout.addWidget(icon_label)
            symbol_icon_labels[symbol] = icon_label

            if coin_name == "":
                text = coin_symbol
            else:
                text = f"{coin_rank} - {coin_name} ({coin_symbol})"
            text_label = QLabel(text, card)
            this_layout.addWidget(text_label)

            self._add_spacer(this_layout, vertical=False)

        card_layout.addItem(input_layout)

    def _add_small_spacing(self, layout: QVBoxLayout) -> None:
        """Add small vertical spacing."""
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        layout.addWidget(spacing_text)

    def _build_confirmation_card(
        self,
        cards_layout: QVBoxLayout,
        symbol_checkboxes: dict[str, QCheckBox],
    ) -> None:
        """Build the confirmation button card."""

        async def job_cf() -> None:
            selected_symbols: list[str] = []
            for symbol, checkbox in symbol_checkboxes.items():
                is_checked = checkbox.isChecked()
                if is_checked:
                    selected_symbols.append(symbol)

            if not MIN_SELECTED_COINS <= len(selected_symbols) <= MAX_SELECTED_COINS:
                await ask(
                    "Select a proper number of coins",
                    "You can select a minimum of 1 and a maximum of 12.",
                    ["Okay"],
                )
            else:
                answer = await ask(
                    "Okay to proceed?",
                    "You cannot change your selections unless you make a new data"
                    " folder.",
                    ["No", "Yes"],
                )
                if answer in (0, 1):
                    return
                self.is_closed = True
                self.result = selected_symbols
                self.done_event.set()

        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        confirm_button = QPushButton("Okay", card)
        outsource(confirm_button.clicked, job_cf)
        confirm_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

    def _load_coin_icons_async(
        self,
        api_requester: ApiRequester,
        symbol_icon_labels: dict[str, QLabel],
        coin_icon_urls: dict[str, str],
    ) -> None:
        """Load coin icons asynchronously."""

        async def draw_icons() -> None:
            for symbol, icon_label in symbol_icon_labels.items():
                coin_symbol = symbol.removesuffix(self.asset_token)
                coin_icon_url = coin_icon_urls.get(coin_symbol, "")
                if coin_icon_url == "":
                    continue
                image_data = await api_requester.bytes(coin_icon_url)
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)

                if self.is_closed:
                    return

                icon_label.setPixmap(pixmap)

        spawn(draw_icons())
