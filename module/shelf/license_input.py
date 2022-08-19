import getmac

from PySide6 import QtWidgets, QtCore, QtGui

from module import core
from module.instrument.api_requester import ApiRequester
from module.instrument.api_request_error import ApiRequestError
from module.widget.horizontal_divider import HorizontalDivider
from module.recipe import user_settings
from module.recipe import outsource


class LicenseInput(QtWidgets.QWidget):
    def __init__(self, done_event, payload):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ prepare the api requester ■■■■■

        api_requester = ApiRequester()

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)
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
        divider = HorizontalDivider(self)
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
                user_settings.apply_app_settings({"license_key": license_key})
                user_settings.load()
                done_event.set()
            except ApiRequestError:
                question = [
                    "License key not valid",
                    "You have to provide a valid license key.",
                    ["Okay"],
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
