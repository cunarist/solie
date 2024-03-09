import asyncio

from PySide6 import QtCore, QtGui, QtWidgets

import solie
from solie.definition.api_requester import ApiRequester
from solie.utility import outsource, user_settings
from solie.widget.horizontal_divider import HorizontalDivider


class CoinSelection(QtWidgets.QWidget):
    def __init__(self, done_event: asyncio.Event, payload):
        super().__init__()
        self.is_closed = False

        asyncio.create_task(self.fill(done_event))

    async def fill(self, done_event):
        # ■■■■■ for remembering ■■■■■

        api_requester = ApiRequester()
        symbol_checkboxes = {}

        # ■■■■■ get previous things ■■■■■

        asset_token = user_settings.get_data_settings()["asset_token"]

        # ■■■■■ get available symbols ■■■■■

        available_symbols = []

        response = await api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload={},
        )
        about_symbols = response["symbols"]
        for about_symbol in about_symbols:
            symbol = about_symbol["symbol"]
            if symbol.endswith(asset_token):
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

        # ■■■■■ sort symbols by rank ■■■■■

        for rank in range(250, 0, -1):
            if rank not in coin_ranks.values():
                continue
            index_to_find = list(coin_ranks.values()).index(rank)
            coin_symbol = list(coin_ranks.keys())[index_to_find]
            symbol = coin_symbol + asset_token
            if symbol not in available_symbols:
                continue
            original_index = available_symbols.index(symbol)
            available_symbols.insert(0, available_symbols.pop(original_index))

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
        detail_text.setText(
            "These are all available coins on Binance."
            "\nYou can select a minimum of 1 and a maximum of 12."
        )
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
        symbol_icon_labels = {}
        input_layout = QtWidgets.QGridLayout()
        blank_coin_pixmap = QtGui.QPixmap()
        blank_coin_pixmap.load(f"{solie.PATH}/static/icon/blank_coin.png")
        for turn, symbol in enumerate(available_symbols):
            coin_symbol = symbol.removesuffix(asset_token)
            coin_name = coin_names.get(coin_symbol, "")
            coin_rank = coin_ranks.get(coin_symbol, 0)
            this_layout = QtWidgets.QHBoxLayout()
            row = turn // 2
            column = turn % 2
            input_layout.addLayout(this_layout, row, column)
            checkbox = QtWidgets.QCheckBox(card)
            symbol_checkboxes[symbol] = checkbox
            this_layout.addWidget(checkbox)
            icon_label = QtWidgets.QLabel("", card)
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

        # confirm function
        async def job_cf(*args):
            data_settings = {}
            selected_symbols = []
            for symbol, checkbox in symbol_checkboxes.items():
                is_checked = checkbox.isChecked()
                if is_checked:
                    selected_symbols.append(symbol)
            if 1 <= len(selected_symbols) <= 12:
                is_symbol_count_ok = True
                data_settings["target_symbols"] = selected_symbols
            else:
                is_symbol_count_ok = False
                question = [
                    "Select a proper number of coins",
                    "You can select a minimum of 1 and a maximum of 12.",
                    ["Okay"],
                ]
                await solie.window.ask(question)
            if is_symbol_count_ok:
                question = [
                    "Okay to proceed?",
                    "You cannot change your selections unless you make a new data"
                    " folder.",
                    ["No", "Yes"],
                ]
                answer = await solie.window.ask(question)
                if answer in (0, 1):
                    return
                await user_settings.apply_data_settings(data_settings)
                await user_settings.load()
                self.is_closed = True
                done_event.set()

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # confirm button
        confirm_button = QtWidgets.QPushButton("Okay", card)
        outsource.do(confirm_button.clicked, job_cf)
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

        async def draw_icons():
            for symbol, icon_label in symbol_icon_labels.items():
                coin_symbol = symbol.removesuffix(asset_token)
                coin_icon_url = coin_icon_urls.get(coin_symbol, "")
                if coin_icon_url == "":
                    continue
                image_data = await api_requester.bytes(coin_icon_url)
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_data)

                if self.is_closed:
                    return

                icon_label.setPixmap(pixmap)

        asyncio.create_task(draw_icons())
