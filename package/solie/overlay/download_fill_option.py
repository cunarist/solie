from asyncio import Event

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from solie.common import outsource


class DownloadFillOption:
    done_event = Event()
    result: int | None

    def __init__(self):
        # ■■■■■ the basic ■■■■■

        super().__init__()
        self.widget = QWidget()

        # ■■■■■ prepare variables ■■■■■

        fill_options = (
            "From 2020 to last year",
            "From first month of this year to last month",
            "This month",
            "Yesterday and the day before yesterday",
        )

        # ■■■■■ full layout ■■■■■

        full_layout = QHBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ spacing ■■■■■

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
        explain_label = QLabel(
            "Solie will fill the candle data with historical data provided by"
            " Binance. The more you fill, the longer it takes. Amount of a few days"
            " only takes few minutes while amount of a few years can take hours."
        )
        explain_label.setWordWrap(True)
        card_layout.addWidget(explain_label)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # option buttons
        for turn, text in enumerate(fill_options):

            async def job(turn=turn):
                self.result = turn
                self.done_event.set()

            option_button = QPushButton(text, card)
            outsource(option_button.clicked, job)
            card_layout.addWidget(option_button)

        # ■■■■■ spacing ■■■■■

        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)

    async def confirm_closing(self) -> bool:
        return True
