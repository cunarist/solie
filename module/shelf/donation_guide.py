from PySide6 import QtWidgets, QtGui, QtCore

from module.widget.horizontal_divider import HorizontalDivider


class DonationGuide(QtWidgets.QWidget):
    def __init__(self, done_event, payload):
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

        # explanation
        detail_text = QtWidgets.QLabel(
            "Description",
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

        # donation guide text
        text = "😉 If you are benefiting from"
        text += " Solie's features and find it helpful,"
        text += " why not consider supporting the Solie project?"
        text += " Your generous donations contribute to"
        text += " the growth and development of Solie."
        text += "\n\nIf you feel like so, please consider"
        text += " using the BUSD(BSC) wallet address written below."
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        card_layout.addWidget(label)

        # address text
        text = "0xF9A7E35254cc8A9A9C811849CAF672F10fAB7366"
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

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        text = "😉 If you are benefiting from"
        text += " Solie's features and find it helpful,"
        text += " why not consider supporting the Solie project?"
        text += " Your generous donations contribute to"
        text += " the growth and development of Solie."
        text += "\n\nIf you feel like so, please consider"
        text += " using the BUSD(BSC) wallet address written below."

        label = QtWidgets.QLabel(text)
        fixed_width_font = QtGui.QFont("Noto Sans", 9)
        label.setFont(fixed_width_font)
        cards_layout.addWidget(label)