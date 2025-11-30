"""Strategy basic information input overlay."""

from asyncio import Event
from re import fullmatch

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from solie.common import PACKAGE_PATH, outsource
from solie.utility import Implements, RiskLevel, Strategy, is_left_version_higher
from solie.widget import HorizontalDivider, OverlayContent, ask

lambda: Implements[OverlayContent](StrategyBasicInput)


class StrategyBasicInput:
    """Overlay for editing strategy basic information."""

    title = "Edit your strategy's basic information"
    close_button = True
    done_event = Event()

    def __init__(self, strategy: Strategy) -> None:
        """Initialize the strategy basic input dialog."""
        super().__init__()
        self.widget = QWidget()
        self.result = None
        self.strategy = strategy

        # Build main layout
        cards_layout = self._create_main_layout()

        # Build cards
        self._build_about_card(cards_layout, strategy)
        self._build_simulation_card(cards_layout, strategy)
        self._build_confirmation_card(cards_layout)

    def _create_main_layout(self) -> QVBoxLayout:
        """Create the main layout structure."""
        full_layout = QHBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # Top spacer
        self._add_spacer(cards_layout, vertical=True)

        return cards_layout

    def _add_spacer(self, layout: QVBoxLayout, vertical: bool = False) -> None:
        """Add a spacer to the layout."""
        if vertical:
            spacer = QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        else:
            spacer = QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        layout.addItem(spacer)

    def _add_small_spacing(self, layout: QVBoxLayout) -> None:
        """Add small vertical spacing."""
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        layout.addWidget(spacing_text)

    def _build_about_card(self, cards_layout: QVBoxLayout, strategy: Strategy) -> None:
        """Build the 'About' information card."""
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # explanation
        detail_text = QLabel()
        detail_text.setText("About")
        detail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        self._add_small_spacing(card_layout)

        divider = HorizontalDivider(self.widget)
        card_layout.addWidget(divider)

        self._add_small_spacing(card_layout)

        # Create form inputs
        this_layout = QFormLayout()
        card_layout.addLayout(this_layout)

        self.code_name_input = QLineEdit()
        self.code_name_input.setText(strategy.code_name)
        this_layout.addRow("Code name", self.code_name_input)

        self.readable_name_input = QLineEdit()
        self.readable_name_input.setText(strategy.readable_name)
        this_layout.addRow("Readable name", self.readable_name_input)

        self.version_input = QLineEdit()
        self.version_input.setText(strategy.version)
        this_layout.addRow("Version", self.version_input)

        self.description_input = QTextEdit()
        self.description_input.setPlainText(strategy.description)
        this_layout.addRow("Description", self.description_input)

        self.risk_level_input = self._create_risk_level_combobox(strategy)
        this_layout.addRow("Risk level", self.risk_level_input)

    def _create_risk_level_combobox(self, strategy: Strategy) -> QComboBox:
        """Create risk level combo box with icons."""
        risk_level_input = QComboBox()
        iconpath = PACKAGE_PATH / "static" / "icon"

        red_pixmap = QPixmap()
        red_pixmap.load(str(iconpath / "traffic_light_red.png"))
        yellow_pixmap = QPixmap()
        yellow_pixmap.load(str(iconpath / "traffic_light_yellow.png"))
        green_pixmap = QPixmap()
        green_pixmap.load(str(iconpath / "traffic_light_green.png"))

        risk_level_input.addItem(green_pixmap, "Low")
        risk_level_input.addItem(yellow_pixmap, "Middle")
        risk_level_input.addItem(red_pixmap, "High")
        risk_level_input.setCurrentIndex(strategy.risk_level.value)

        return risk_level_input

    def _build_simulation_card(
        self,
        cards_layout: QVBoxLayout,
        strategy: Strategy,
    ) -> None:
        """Build the 'Simulation' settings card."""
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        detail_text = QLabel()
        detail_text.setText("Simulation")
        detail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        self._add_small_spacing(card_layout)

        divider = HorizontalDivider(self.widget)
        card_layout.addWidget(divider)

        self._add_small_spacing(card_layout)

        this_layout = QFormLayout()
        card_layout.addLayout(this_layout)

        self.parallelized_input = QCheckBox()
        self.parallelized_input.setChecked(
            bool(strategy.parallel_simulation_chunk_days),
        )
        this_layout.addRow("Parallelized", self.parallelized_input)

        self.chunk_division_input = QSpinBox()
        self.chunk_division_input.setSuffix(" days")
        self.chunk_division_input.setMinimum(7)
        self.chunk_division_input.setMaximum(90)
        self.chunk_division_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.chunk_division_input.setValue(strategy.parallel_simulation_chunk_days or 0)
        this_layout.addRow("Chunk division", self.chunk_division_input)

    def _build_confirmation_card(self, cards_layout: QVBoxLayout) -> None:
        """Build the confirmation button card."""
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        async def job() -> None:
            await self._save_strategy_settings()

        confirm_button = QPushButton("Save and close", card)
        outsource(confirm_button.clicked, job)
        confirm_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # Bottom spacer
        self._add_spacer(cards_layout, vertical=True)

    async def _save_strategy_settings(self) -> None:
        """Save strategy settings with validation."""
        strategy = self.strategy

        strategy.readable_name = self.readable_name_input.text()

        version = self.version_input.text()
        if fullmatch(r"[0-9]+\.[0-9]+", version):
            if not is_left_version_higher(strategy.version, version):
                strategy.version = version
            else:
                await ask(
                    "Version is lower.",
                    "You can't lower the version of your strategy. It should only"
                    " go up higher.",
                    ["Okay"],
                )
                return
        else:
            await ask(
                "Version format is wrong.",
                "You should write the version in two numeric fields, divided by a"
                " single dot.",
                ["Okay"],
            )
            return

        strategy.description = self.description_input.toPlainText()
        strategy.risk_level = RiskLevel(self.risk_level_input.currentIndex())

        parallel = self.parallelized_input.isChecked()
        parallel_chunk_days = self.chunk_division_input.value() if parallel else None
        strategy.parallel_simulation_chunk_days = parallel_chunk_days

        self.done_event.set()

    async def confirm_closing(self) -> bool:
        """Confirm if overlay can be closed."""
        return True
