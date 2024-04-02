import asyncio

from PySide6 import QtCore, QtGui, QtWidgets

import solie
from solie.info import PACKAGE_PATH
from solie.utility.api_requester import ApiRequester
from solie.utility.outsource import outsource
from solie.widget.horizontal_divider import HorizontalDivider

from .base_overlay import BaseOverlay


class TokenSelection(BaseOverlay):
    def __init__(self):
        super().__init__()
        self.is_closed = False

        asyncio.create_task(self.fill(self.done_event))

    async def fill(self, done_event):
        # ■■■■■ for remembering ■■■■■

        token_radioboxes: dict[str, QtWidgets.QRadioButton] = {}

        # ■■■■■ prepare the api requester ■■■■■

        api_requester = ApiRequester()

        # ■■■■■ get all symbols ■■■■■

        available_symbols = []

        response = await api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload={},
        )
        about_symbols = response["symbols"]
        for about_symbol in about_symbols:
            symbol = about_symbol["symbol"]
            available_symbols.append(symbol)

        # ■■■■■ get coin informations ■■■■■

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

        # ■■■■■ set things ■■■■■

        available_tokens = ["USDT", "BUSD"]
        number_of_markets = {token: 0 for token in available_tokens}

        for symbol in available_symbols:
            for token in available_tokens:
                if symbol.endswith(token):
                    number_of_markets[token] += 1

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ spacing ■■■■■

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # explanation
        detail_text = QtWidgets.QLabel()
        detail_text.setText("These are all available tokens on Binance.")
        detail_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # divider
        divider = HorizontalDivider(self)
        card_layout.addWidget(divider)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # input
        token_icon_labels = {}
        input_layout = QtWidgets.QGridLayout()
        blank_coin_pixmap = QtGui.QPixmap()
        blank_coin_pixmap.load(str(PACKAGE_PATH / "static" / "icon/blank_coin.png"))
        for turn, token in enumerate(available_tokens):
            this_layout = QtWidgets.QHBoxLayout()
            row = turn // 2
            column = turn % 2
            input_layout.addLayout(this_layout, row, column)
            radiobutton = QtWidgets.QRadioButton(card)
            token_radioboxes[token] = radiobutton
            this_layout.addWidget(radiobutton)
            icon_label = QtWidgets.QLabel("", card)
            icon_label.setPixmap(blank_coin_pixmap)
            icon_label.setScaledContents(True)
            icon_label.setFixedSize(40, 40)
            icon_label.setMargin(5)
            this_layout.addWidget(icon_label)
            token_icon_labels[token] = icon_label
            text = f"{token} ({number_of_markets[token]} coins available)"
            text_label = QtWidgets.QLabel(text, card)
            this_layout.addWidget(text_label)
            spacer = QtWidgets.QSpacerItem(
                0,
                0,
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Minimum,
            )
            this_layout.addItem(spacer)
        card_layout.addItem(input_layout)

        # ■■■■■ a card ■■■■■

        self.result: str

        # confirm function
        async def job_cf(*args):
            selected_tokens = []
            for symbol, radiobox in token_radioboxes.items():
                is_selected = radiobox.isChecked()
                if is_selected:
                    selected_tokens.append(symbol)
            if len(selected_tokens) == 0:
                await solie.window.ask(
                    "Nothing selected",
                    "Choose one of the tokens.",
                    ["Okay"],
                )
            if len(selected_tokens) == 1:
                answer = await solie.window.ask(
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
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # confirm button
        confirm_button = QtWidgets.QPushButton("Okay", card)
        outsource(confirm_button.clicked, job_cf)
        confirm_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # ■■■■■ spacing ■■■■■

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)

        # ■■■■■ draw coin icons from another task ■■■■■

        async def job_dc():
            for token, icon_label in token_icon_labels.items():
                coin_icon_url = coin_icon_urls.get(token, "")
                if coin_icon_url == "":
                    continue
                image_data = await api_requester.bytes(coin_icon_url)
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_data)

                if self.is_closed:
                    return

                icon_label.setPixmap(pixmap)

        asyncio.create_task(job_dc())
