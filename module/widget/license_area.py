import threading
import getmac

from PyQt6 import QtWidgets, QtCore, QtGui

from module.instrument.api_requester import ApiRequester
from module.instrument.api_request_error import ApiRequestError
from module.recipe import standardize
from module.recipe import outsource


class LicenseArea(QtWidgets.QScrollArea):

    done_event = threading.Event()

    def __init__(self, root):

        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ prepare the api requester ■■■■■

        api_requester = ApiRequester()

        # ■■■■■ full structure ■■■■■

        self.setWidgetResizable(True)

        # ■■■■■ full layout ■■■■■

        full_widget = QtWidgets.QWidget()
        self.setWidget(full_widget)
        full_layout = QtWidgets.QHBoxLayout(full_widget)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ top spacing ■■■■■

        # spacing
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
            "쏠쏠 라이센스 키를 입력하세요.",
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
            "정확히 입력해야 합니다.",
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
        this_layout = QtWidgets.QHBoxLayout()
        card_layout.addLayout(this_layout)
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(spacer)
        key_input = QtWidgets.QLineEdit()
        key_input.setFixedWidth(360)
        key_input.setMaxLength(32)
        key_input.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        this_layout.addWidget(key_input)
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(spacer)

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        card_layout.addItem(spacer)

        # ■■■■■ a card ■■■■■

        # function for checking license key
        def job(*args):
            widget = key_input
            license_key = root.undertake(lambda w=widget: w.text(), True)
            try:
                payload = {
                    "licenseKey": license_key,
                    "macAddress": getmac.get_mac_address(),
                }
                api_requester.cunarist("PUT", "/api/solsol/key-mac-pair", payload)
                standardize.set_license_key(license_key)
                self.done_event.set()
            except ApiRequestError:
                question = [
                    "유효한 라이센스 키가 아닙니다.",
                    "정확한 라이센스 키를 입력해야 합니다.",
                    ["확인"],
                    False,
                ]
                root.ask(question)

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        cards_layout.addWidget(card)

        # confirm button
        confirm_button = QtWidgets.QPushButton("확인", card)
        outsource.do(confirm_button.clicked, job)
        confirm_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # ■■■■■ bottom spacing ■■■■■

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)
