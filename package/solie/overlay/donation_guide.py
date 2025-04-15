from asyncio import Event

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class DonationGuide:
    done_event = Event()
    result = None

    def __init__(self):
        # ■■■■■ the basic ■■■■■

        super().__init__()
        self.widget = QWidget()

        # ■■■■■ full layout ■■■■■

        full_layout = QHBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ spacing ■■■■■

        # spacing
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

        # donation guide text
        text = "😉 If you are benefiting from"
        text += " Solie's features and find it helpful,"
        text += " why not consider supporting the Solie project?"
        text += " Your generous donations contribute to"
        text += " the growth and development of Solie."
        text += "\n\nIf you feel like so, please consider"
        text += " using the USDT(ETH mainnet) wallet address written below."
        label = QLabel(text)
        label.setWordWrap(True)
        card_layout.addWidget(label)

        # address text
        text = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        lineedit_widget = QLineEdit(text)
        lineedit_widget.setReadOnly(True)
        lineedit_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lineedit_widget)

        # ■■■■■ spacing ■■■■■

        # spacing
        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)

    async def confirm_closing(self) -> bool:
        return True
