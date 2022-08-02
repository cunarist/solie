import threading
import urllib

from PyQt6 import QtWidgets, QtCore, QtGui

from module.instrument.api_requester import ApiRequester
from module.recipe import standardize
from module.recipe import outsource
from module.recipe import thread_toss


class TokenSelectionArea(QtWidgets.QScrollArea):

    done_event = threading.Event()

    def __init__(self, root):

        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ for remembering ■■■■■

        token_radioboxes = {}

        # ■■■■■ prepare the api requester ■■■■■

        api_requester = ApiRequester()

        # ■■■■■ get all symbols ■■■■■

        response = api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload={},
        )
        about_symbols = response["symbols"]
        available_symbols = []
        for about_symbol in about_symbols:
            symbol = about_symbol["symbol"]
            available_symbols.append(symbol)

        # ■■■■■ get coin informations ■■■■■

        response = api_requester.coinstats("GET", "/public/v1/coins")
        about_coins = response["coins"]
        coin_names = {}
        coin_icon_urls = {}
        coin_ranks = {}
        for about_coin in about_coins:
            coin_symbol = about_coin["symbol"]
            coin_names[coin_symbol] = about_coin["name"]
            coin_icon_urls[coin_symbol] = about_coin["icon"]
            coin_ranks[coin_symbol] = about_coin["rank"]

        # ■■■■■ prepare confirm function ■■■■■

        def job(*args):
            basics = {}
            selected_tokens = []
            for symbol, radiobox in token_radioboxes.items():
                is_selected = root.undertake(lambda: radiobox.isChecked(), True)
                if is_selected:
                    selected_tokens.append(symbol)
            if len(selected_tokens) == 1:
                is_symbol_count_ok = True
                basics["asset_token"] = selected_tokens[0]
            else:
                is_symbol_count_ok = False
                question = [
                    "선택하세요.",
                    "아무것도 선택되어 있지 않습니다.",
                    ["확인"],
                    False,
                ]
                root.ask(question)
            if is_symbol_count_ok:
                question = [
                    "이대로 결정하시겠어요?",
                    "이 토큰에 기반한 바이낸스 선물 시장을 사용하게 됩니다.",
                    ["아니오", "예"],
                    False,
                ]
                answer = root.ask(question)
                if answer in (0, 1):
                    return
                standardize.apply_basics(basics)
                self.done_event.set()

        # ■■■■■ set things ■■■■■

        available_tokens = []
        for symbol in available_symbols:
            if "_" in symbol:
                continue
            if symbol.startswith("BTC"):
                token = symbol.removeprefix("BTC")
                available_tokens.append(token)
        available_tokens = ["USDT", "BUSD"]
        number_of_markets = {token: 0 for token in available_tokens}

        for symbol in available_symbols:
            for token in available_tokens:
                if symbol.endswith(token):
                    number_of_markets[token] += 1

        # ■■■■■ full structure ■■■■■

        self.setWidgetResizable(True)

        # ■■■■■ full layout ■■■■■

        full_widget = QtWidgets.QWidget()
        self.setWidget(full_widget)
        full_layout = QtWidgets.QHBoxLayout(full_widget)
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
        card = QtWidgets.QGroupBox(objectName="card")
        card.setFixedWidth(720)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # title
        main_text = QtWidgets.QLabel(
            "자산 저장에 사용할 토큰을 선택하세요.",
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        main_text_font = QtGui.QFont()
        main_text_font.setPointSize(12)
        main_text.setFont(main_text_font)
        main_text.setWordWrap(True)
        card_layout.addWidget(main_text)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # explanation
        detail_text = QtWidgets.QLabel(
            "바이낸스 선물 시장에서 사용 가능한 자산 저장 토큰입니다.",
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # divider
        divider = QtWidgets.QFrame(self)
        divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        divider.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
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
        blank_coin_pixmap.load("./resource/icon/blank_coin.png")
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
            text = f"{token} ({number_of_markets[token]}개 코인 거래 가능)"
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

        # card structure
        card = QtWidgets.QGroupBox(objectName="card")
        card.setFixedWidth(720)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # confirm button
        confirm_button = QtWidgets.QPushButton("결정", card)
        outsource.do(confirm_button.clicked, job)
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

        # ■■■■■ draw crypto icons from another thread ■■■■■

        def job():
            for token, icon_label in token_icon_labels.items():
                coin_icon_url = coin_icon_urls.get(token, "")
                if coin_icon_url == "":
                    continue
                image_data = urllib.request.urlopen(coin_icon_url).read()
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_data)

                def job(icon_label=icon_label, pixmap=pixmap):
                    icon_label.setPixmap(pixmap)

                root.undertake(job, False)

        thread_toss.apply_async(job)
