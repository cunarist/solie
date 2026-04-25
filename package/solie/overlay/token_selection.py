"""Asset token selection overlay."""

from asyncio import Event
from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from solie.common import PACKAGE_PATH, outsource, spawn
from solie.utility import ApiRequester
from solie.widget import HorizontalDivider, ask


class Availables(NamedTuple):
    """Available tokens and symbols for selection."""

    tokens: set[str]
    symbols: set[str]


class TokenSelection:
    """Overlay for selecting asset token."""

    title = "Choose a token to treat as your asset"
    close_button = False
    done_event = Event()

    def __init__(self) -> None:
        """Initialize token selection overlay."""
        super().__init__()
        self.widget = QWidget()
        self.result: str

        self.is_closed = False
        spawn(self.fill())

    async def confirm_closing(self) -> bool:
        """Confirm if overlay can be closed."""
        return True

    async def fill(self) -> None:
        """Fill the token selection UI with available tokens."""
        api_requester = ApiRequester()

        # Fetch token and coin data
        available_tokens, available_symbols = await self._fetch_availables(
            api_requester,
        )
        coin_icon_urls = await self._fetch_coin_metadata(api_requester)
        number_of_markets = self._calculate_market_counts(
            available_tokens,
            available_symbols,
        )

        # Build UI
        token_icon_labels = self._build_ui(available_tokens, number_of_markets)

        # Load coin icons asynchronously
        self._load_coin_icons_async(api_requester, token_icon_labels, coin_icon_urls)

    async def _fetch_availables(self, api_requester: ApiRequester) -> Availables:
        """Fetch available tokens and symbols from Binance."""
        available_tokens = set[str]()
        available_symbols = set[str]()

        response = await api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload={},
        )
        about_symbols = response["symbols"]
        for about_symbol in about_symbols:
            token = about_symbol["marginAsset"]
            available_tokens.add(token)
            symbol = about_symbol["symbol"]
            available_symbols.add(symbol)

        return Availables(available_tokens, available_symbols)

    async def _fetch_coin_metadata(self, api_requester: ApiRequester) -> dict[str, str]:
        """Fetch coin metadata from CoinGecko."""
        response = await api_requester.coingecko(
            "GET",
            "/api/v3/coins/markets",
            {
                "vs_currency": "usd",
            },
        )

        coin_icon_urls: dict[str, str] = {}
        for about_coin in response:
            raw_symbol: str = about_coin["symbol"]
            coin_symbol = raw_symbol.upper()
            coin_icon_urls[coin_symbol] = about_coin["image"]

        return coin_icon_urls

    def _calculate_market_counts(
        self,
        available_tokens: set[str],
        available_symbols: set[str],
    ) -> dict[str, int]:
        """Calculate number of markets for each token."""
        number_of_markets = dict.fromkeys(available_tokens, 0)

        for symbol in available_symbols:
            for token in available_tokens:
                if symbol.endswith(token):
                    number_of_markets[token] += 1

        return number_of_markets

    def _build_ui(
        self,
        available_tokens: set[str],
        number_of_markets: dict[str, int],
    ) -> dict[str, QLabel]:
        """Build the main UI layout."""
        token_radioboxes: dict[str, QRadioButton] = {}
        token_icon_labels: dict[str, QLabel] = {}
        """Build the main UI layout."""
        token_radioboxes: dict[str, QRadioButton] = {}
        token_icon_labels: dict[str, QLabel] = {}

        full_layout = QHBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # Top spacer
        self._add_spacer(cards_layout, vertical=True)

        # Build token selection card
        self._build_token_selection_card(
            cards_layout,
            available_tokens,
            number_of_markets,
            token_radioboxes,
            token_icon_labels,
        )

        # Build confirmation card
        self._build_confirmation_card(cards_layout, token_radioboxes)

        # Bottom spacer
        self._add_spacer(cards_layout, vertical=True)

        return token_icon_labels

    def _add_spacer(
        self,
        layout: QVBoxLayout | QHBoxLayout,
        vertical: bool = False,
    ) -> None:
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

    def _build_token_selection_card(
        self,
        cards_layout: QVBoxLayout,
        available_tokens: set[str],
        number_of_markets: dict[str, int],
        token_radioboxes: dict[str, QRadioButton],
        token_icon_labels: dict[str, QLabel],
    ) -> None:
        """Build the card with token radio buttons."""
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        detail_text = QLabel()
        detail_text.setText("These are all the available tokens on Binance.")
        detail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        self._add_small_spacing(card_layout)

        divider = HorizontalDivider(self.widget)
        card_layout.addWidget(divider)

        self._add_small_spacing(card_layout)

        input_layout = QGridLayout()
        blank_coin_pixmap = QPixmap()
        blank_coin_pixmap.load(str(PACKAGE_PATH / "static" / "icon/blank_coin.png"))

        for turn, token in enumerate(sorted(available_tokens)):
            this_layout = QHBoxLayout()
            row = turn // 2
            column = turn % 2
            input_layout.addLayout(this_layout, row, column)

            radiobutton = QRadioButton(card)
            token_radioboxes[token] = radiobutton
            this_layout.addWidget(radiobutton)

            icon_label = QLabel("", card)
            icon_label.setPixmap(blank_coin_pixmap)
            icon_label.setScaledContents(True)
            icon_label.setFixedSize(40, 40)
            icon_label.setMargin(5)
            this_layout.addWidget(icon_label)
            token_icon_labels[token] = icon_label

            text = f"{token} ({number_of_markets[token]} coins available)"
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
        token_radioboxes: dict[str, QRadioButton],
    ) -> None:
        """Build the confirmation button card."""

        async def job_cf() -> None:
            selected_tokens: list[str] = []
            for symbol, radiobox in token_radioboxes.items():
                is_selected = radiobox.isChecked()
                if is_selected:
                    selected_tokens.append(symbol)

            if len(selected_tokens) == 0:
                await ask(
                    "Nothing selected",
                    "Choose one of the tokens.",
                    ["Okay"],
                )
                return

            if len(selected_tokens) == 1:
                answer = await ask(
                    "Okay to proceed?",
                    "Solie will treat this token as your asset.",
                    ["No", "Yes"],
                )
                if answer in (0, 1):
                    return
                self.is_closed = True
                self.result = selected_tokens[0]
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
        token_icon_labels: dict[str, QLabel],
        coin_icon_urls: dict[str, str],
    ) -> None:
        """Load coin icons asynchronously."""

        async def job_dc() -> None:
            for token, icon_label in token_icon_labels.items():
                coin_icon_url = coin_icon_urls.get(token, "")
                if coin_icon_url == "":
                    continue
                image_data = await api_requester.bytes(coin_icon_url)
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)

                if self.is_closed:
                    return

                icon_label.setPixmap(pixmap)

        spawn(job_dc())
