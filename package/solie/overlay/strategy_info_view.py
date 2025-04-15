from asyncio import Event

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from solie.utility import Strategy
from solie.widget import HorizontalDivider


class StrategyInfoView:
    done_event = Event()
    result = None

    def __init__(self, strategy: Strategy):
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

        # explanation
        detail_text = QLabel()
        detail_text.setText("Description")
        detail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # spacing
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # divider
        divider = HorizontalDivider(self.widget)
        card_layout.addWidget(divider)

        # spacing
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # explanation
        detail_text = QLabel(strategy.description)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

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
