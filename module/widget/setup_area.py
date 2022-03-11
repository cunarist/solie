from datetime import datetime, timezone
import threading
import urllib

from PyQt6 import QtWidgets, QtCore, QtGui

from instrument.api_requester import ApiRequester
from recipe import standardize
from recipe import outsource
from recipe import thread_toss


class SetupArea(QtWidgets.QScrollArea):

    done_event = threading.Event()

    def __init__(self, root):

        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ for remembering ■■■■■

        symbol_checkboxes = {}

        # ■■■■■ prepare the api requester ■■■■■

        api_requester = ApiRequester()

        # ■■■■■ get available symbols ■■■■■

        response = api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload={},
        )
        about_symbols = response["symbols"]
        available_symbols = []
        for about_symbol in about_symbols:
            symbol = about_symbol["symbol"]
            if symbol.endswith("USDT"):
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

        # ■■■■■ sort symbols by rank ■■■■■

        for rank in range(250, 0, -1):
            if rank not in coin_ranks.values():
                continue
            index_to_find = list(coin_ranks.values()).index(rank)
            coin_symbol = list(coin_ranks.keys())[index_to_find]
            symbol = coin_symbol + "USDT"
            if symbol not in available_symbols:
                continue
            original_index = available_symbols.index(symbol)
            available_symbols.insert(0, available_symbols.pop(original_index))

        # ■■■■■ prepare confirm function ■■■■■

        def job(*args):
            basics = {}
            basics["generated_timestamp"] = int(datetime.now(timezone.utc).timestamp())
            selected_symbols = []
            for symbol, checkbox in symbol_checkboxes.items():
                is_checked = root.undertake(lambda: checkbox.isChecked(), True)
                if is_checked:
                    selected_symbols.append(symbol)
            if 1 <= len(selected_symbols) <= 10:
                is_symbol_count_ok = True
                basics["target_symbols"] = selected_symbols
            else:
                is_symbol_count_ok = False
                question = [
                    "적절한 개수의 심볼을 선택하세요.",
                    "1개 이상 10개 이하의 심볼을 선택해야 합니다.",
                    ["확인"],
                ]
                root.ask(question)
            if is_symbol_count_ok:
                question = [
                    "이대로 결정하시겠어요?",
                    "정한 이후 데이터 저장 폴더를 바꾸기 전까지는 변경할 수 없습니다.",
                    ["아니오", "예"],
                ]
                answer = root.ask(question)
                if answer in (0, 1):
                    return
                standardize.set_basics(basics)
                self.done_event.set()

        # ■■■■■ full structure ■■■■■

        self.setWidgetResizable(True)

        # ■■■■■ full layout ■■■■■

        full_widget = QtWidgets.QWidget()
        self.setWidget(full_widget)
        full_layout = QtWidgets.QHBoxLayout(full_widget)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox(objectName="card")
        card.setFixedWidth(720)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        cards_layout.addWidget(card)

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        card_layout.addItem(spacer)

        # title
        main_text = QtWidgets.QLabel(
            "사용할 코인을 선택하세요.",
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
            "바이낸스에서 사용 가능한 모든 코인입니다.\n최소 1개, 최대 10개를 선택할 수 있습니다.",
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

        # input
        symbol_icon_labels = {}
        input_layout = QtWidgets.QGridLayout()
        blank_coin_pixmap = QtGui.QPixmap()
        blank_coin_pixmap.load("./resource/icon/blank_coin.png")
        for turn, symbol in enumerate(available_symbols):
            coin_symbol = symbol.removesuffix("USDT")
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

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        card_layout.addItem(spacer)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox(objectName="card")
        card.setFixedWidth(720)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        cards_layout.addWidget(card)

        # confirm button
        confirm_button = QtWidgets.QPushButton("결정", card)
        outsource.do(confirm_button.clicked, job)
        confirm_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # ■■■■■ draw crypto icons from another thread ■■■■■

        def job():
            for symbol, icon_label in symbol_icon_labels.items():
                coin_symbol = symbol.removesuffix("USDT")
                coin_icon_url = coin_icon_urls.get(coin_symbol, "")
                if coin_icon_url == "":
                    continue
                image_data = urllib.request.urlopen(coin_icon_url).read()
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_data)

                def job(icon_label=icon_label, pixmap=pixmap):
                    icon_label.setPixmap(pixmap)

                root.undertake(job, False)

        thread_toss.apply_async(job)
