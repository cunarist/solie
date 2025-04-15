from asyncio import Event

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


class TokenSelection:
    done_event = Event()
    result: str

    def __init__(self):
        super().__init__()
        self.widget = QWidget()
        self.is_closed = False

        spawn(self.fill(self.done_event))

    async def confirm_closing(self) -> bool:
        return True

    async def fill(self, done_event):
        # ■■■■■ for remembering ■■■■■

        token_radioboxes: dict[str, QRadioButton] = {}

        # ■■■■■ prepare the api requester ■■■■■

        api_requester = ApiRequester()

        # ■■■■■ get all symbols ■■■■■

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

        # ■■■■■ get coin informations ■■■■■

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

        # ■■■■■ set things ■■■■■

        number_of_markets = {token: 0 for token in available_tokens}

        for symbol in available_symbols:
            for token in available_tokens:
                if symbol.endswith(token):
                    number_of_markets[token] += 1

        # ■■■■■ full layout ■■■■■

        full_layout = QHBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ spacing ■■■■■

        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # explanation
        detail_text = QLabel()
        detail_text.setText("These are all the available tokens on Binance.")
        detail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # spacing
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # divider
        divider = HorizontalDivider(self.widget)
        card_layout.addWidget(divider)

        # spacing
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # input
        token_icon_labels: dict[str, QLabel] = {}
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
            spacer = QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
            this_layout.addItem(spacer)
        card_layout.addItem(input_layout)

        # ■■■■■ a card ■■■■■

        # confirm function
        async def job_cf():
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

        # card structure
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # confirm button
        confirm_button = QPushButton("Okay", card)
        outsource(confirm_button.clicked, job_cf)
        confirm_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # ■■■■■ spacing ■■■■■

        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)

        # ■■■■■ draw coin icons from another task ■■■■■

        async def job_dc():
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
