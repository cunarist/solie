from PySide6 import QtCore, QtWidgets

from .base_overlay import BaseOverlay


class DonationGuide(BaseOverlay):
    def __init__(self):
        # ■■■■■ the basic ■■■■■

        super().__init__()

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

        # donation guide text
        text = "😉 If you are benefiting from"
        text += " Solie's features and find it helpful,"
        text += " why not consider supporting the Solie project?"
        text += " Your generous donations contribute to"
        text += " the growth and development of Solie."
        text += "\n\nIf you feel like so, please consider"
        text += " using the USDT(ETH mainnet) wallet address written below."
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        card_layout.addWidget(label)

        # address text
        text = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        lineedit_widget = QtWidgets.QLineEdit(text)
        lineedit_widget.setReadOnly(True)
        lineedit_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lineedit_widget)

        # ■■■■■ spacing ■■■■■

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)
