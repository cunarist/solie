"""Download fill option selection overlay."""

from asyncio import Event
from datetime import UTC, datetime
from enum import Enum
from typing import NamedTuple

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from solie.common import outsource
from solie.widget import HorizontalDivider, ask

MIN_YEAR = 2009


class DownloadYearRange(NamedTuple):
    """Range of years for historical data download."""

    start: int  # Inclusive
    end: int  # Inclusive


class DownloadFillOption(Enum):
    """Predefined time ranges for filling historical data."""

    FROM_YEAR_START_TO_LAST_MONTH = 0
    THIS_MONTH = 1
    LAST_TWO_DAYS = 2


FILL_OPTIONS_TEXTS = (
    "From first month of this year to last month",
    "This month",
    "Yesterday and the day before yesterday",
)


class DownloadFillOptionChooser:
    """Overlay for choosing historical data download range."""

    title = "Choose the range to fill"
    close_button = True
    done_event = Event()

    def __init__(self) -> None:
        """Initialize download fill option chooser."""
        super().__init__()
        self.widget = QWidget()
        self.result: DownloadYearRange | DownloadFillOption | None = None

        current_year = datetime.now(UTC).year

        # Create main layout
        full_layout = QHBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # Add top spacer
        self._add_spacer(cards_layout)

        # Create UI cards
        self._create_explanation_card(cards_layout)
        self._create_year_range_card(cards_layout, current_year)

        # Add bottom spacer
        self._add_spacer(cards_layout)

    def _add_spacer(self, layout: QVBoxLayout) -> None:
        """Add expanding spacer to layout."""
        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        layout.addItem(spacer)

    def _create_explanation_card(self, parent_layout: QVBoxLayout) -> None:
        """Create explanation card."""
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        parent_layout.addWidget(card)

        explain_label = QLabel(
            "Solie will fill the candle data with historical data provided by"
            " Binance. The more you fill, the longer it takes. Amount of a few days"
            " only takes few minutes while amount of a few years can take hours.",
        )
        explain_label.setWordWrap(True)
        card_layout.addWidget(explain_label)

    def _create_year_range_card(
        self,
        parent_layout: QVBoxLayout,
        current_year: int,
    ) -> None:
        """Create year range selection card."""
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        parent_layout.addWidget(card)

        last_year = current_year - 1

        # Add year range inputs
        self._add_year_range_inputs(card, card_layout, last_year)

        # Add fill option buttons
        self._add_fill_option_buttons(card, card_layout)

    def _add_year_range_inputs(
        self,
        card: QGroupBox,
        card_layout: QVBoxLayout,
        last_year: int,
    ) -> None:
        """Add year range input controls."""
        button_layout = QHBoxLayout()
        card_layout.addLayout(button_layout)
        card_layout.addWidget(HorizontalDivider(self.widget))

        from_label = QLabel("From")
        button_layout.addWidget(from_label)

        self.year_from_input = QSpinBox()
        self.year_from_input.setMinimum(MIN_YEAR)
        self.year_from_input.setMaximum(last_year)
        self.year_from_input.setValue(last_year)
        self.year_from_input.setMaximumWidth(100)
        button_layout.addWidget(self.year_from_input)

        to_label = QLabel("to")
        button_layout.addWidget(to_label)

        self.year_to_input = QSpinBox()
        self.year_to_input.setMinimum(MIN_YEAR)
        self.year_to_input.setMaximum(last_year)
        self.year_to_input.setValue(last_year)
        self.year_to_input.setMaximumWidth(100)
        button_layout.addWidget(self.year_to_input)

        option_button = QPushButton("Custom year range", card)
        option_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        button_layout.addWidget(option_button)

        async def custom_job() -> None:
            year_from = self.year_from_input.value()
            year_to = self.year_to_input.value()
            if year_from <= year_to:
                self.result = DownloadYearRange(start=year_from, end=year_to)
                self.done_event.set()
            else:
                await ask(
                    "Invalid year range",
                    "Start year must be less than or equal to end year.",
                    ["Okay"],
                )

        outsource(option_button.clicked, custom_job)

    def _add_fill_option_buttons(
        self,
        card: QGroupBox,
        card_layout: QVBoxLayout,
    ) -> None:
        """Add preset fill option buttons."""
        for turn, text in enumerate(FILL_OPTIONS_TEXTS):

            async def job(turn: int = turn) -> None:
                self.result = DownloadFillOption(turn)
                self.done_event.set()

            option_button = QPushButton(text, card)
            outsource(option_button.clicked, job)
            card_layout.addWidget(option_button)

    async def confirm_closing(self) -> bool:
        """Confirm if overlay can be closed."""
        return True
