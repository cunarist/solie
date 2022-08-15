import threading
import getmac

from PySide6 import QtWidgets, QtCore, QtGui

from module import core
from module.instrument.api_requester import ApiRequester
from module.instrument.api_request_error import ApiRequestError
from module.recipe import user_settings
from module.recipe import outsource


class LicenseArea(QtWidgets.QScrollArea):
    done_event = threading.Event()

    def __init__(self):
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

        # ■■■■■ spacing ■■■■■

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
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # title
        main_text = QtWidgets.QLabel(
            "Enter Solsol license key",
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
            "Make sure there are no typos.",
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
        this_layout = QtWidgets.QHBoxLayout()
        card_layout.addLayout(this_layout)
        key_input = QtWidgets.QLineEdit()
        key_input.setFixedWidth(360)
        key_input.setMaxLength(32)
        key_input.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        this_layout.addWidget(key_input)

        # ■■■■■ a card ■■■■■

        # function for checking license key
        def job(*args):
            widget = key_input
            license_key = core.window.undertake(lambda w=widget: w.text(), True)
            try:
                payload = {
                    "licenseKey": license_key,
                    "macAddress": getmac.get_mac_address(),
                }
                api_requester.cunarist("PUT", "/api/solsol/key-mac-pair", payload)
                user_settings.set_license_key(license_key)
                self.done_event.set()
            except ApiRequestError:
                question = [
                    "License key not valid",
                    "You have to provide a valid license key.",
                    ["Okay"],
                    False,
                ]
                core.window.ask(question)

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # confirm button
        confirm_button = QtWidgets.QPushButton("Okay", card)
        outsource.do(confirm_button.clicked, job)
        confirm_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # ■■■■■ spacing ■■■■■

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)
