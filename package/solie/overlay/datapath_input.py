"""Data folder path selection overlay."""

from asyncio import Event
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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
from xdialog import directory

from solie.common import outsource, spawn_blocking
from solie.utility import Cell, Implements
from solie.widget import HorizontalDivider, OverlayContent, ask

lambda: Implements[OverlayContent](DatapathInput)


class DatapathInput:
    """Overlay for selecting data storage directory."""

    title = "Choose your data folder"
    close_button = False
    done_event = Event()

    def __init__(self) -> None:
        """Initialize data path input overlay."""
        super().__init__()
        self.widget = QWidget()
        self.result: Path

        # Create main layout
        full_layout = QHBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # Add top spacer
        self._add_spacer(cards_layout)

        # Create selection card
        self._create_selection_card(cards_layout)

        # Create confirm card
        self._create_confirm_card(cards_layout)

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

    def _create_selection_card(self, parent_layout: QVBoxLayout) -> None:
        """Create folder selection card and return the folder label."""
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        parent_layout.addWidget(card)

        # Description text
        detail_text = QLabel()
        detail_text.setText("All the data that Solie produces will go in this folder.")
        detail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # Spacing
        self._add_text_spacing(card_layout, 3)

        # Divider
        divider = HorizontalDivider(self.widget)
        card_layout.addWidget(divider)

        # Spacing
        self._add_text_spacing(card_layout, 3)

        # Folder path label
        folder_label = QLabel()
        folder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        folder_label.setWordWrap(True)
        card_layout.addWidget(folder_label)

        # Spacing
        self._add_text_spacing(card_layout, 3)

        # Choose folder button
        self._add_choose_button(card, card_layout, folder_label)

    def _add_text_spacing(self, layout: QVBoxLayout, point_size: int) -> None:
        """Add text spacing widget."""
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(point_size)
        spacing_text.setFont(spacing_text_font)
        layout.addWidget(spacing_text)

    def _add_choose_button(
        self,
        card: QGroupBox,
        card_layout: QVBoxLayout,
        folder_label: QLabel,
    ) -> None:
        """Add choose folder button."""
        datapath = Cell[Path | None](None)

        async def job_dp() -> None:
            str_path = await spawn_blocking(directory, title="Data folder")
            path = Path(str_path)
            folder_label.setText(str(path))
            datapath.value = path
            self.result = path

        this_layout = QHBoxLayout()
        card_layout.addLayout(this_layout)
        choose_button = QPushButton("Choose folder", card)
        outsource(choose_button.clicked, job_dp)
        choose_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        this_layout.addWidget(choose_button)

    def _create_confirm_card(
        self,
        parent_layout: QVBoxLayout,
    ) -> None:
        """Create confirm button card."""

        async def job_ac() -> None:
            if not hasattr(self, "result"):
                await ask(
                    "Data folder is not chosen",
                    "Choose your data folder first.",
                    ["Okay"],
                )
            else:
                self.done_event.set()

        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        parent_layout.addWidget(card)

        confirm_button = QPushButton("Okay", card)
        outsource(confirm_button.clicked, job_ac)
        confirm_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        card_layout.addWidget(confirm_button)

    async def confirm_closing(self) -> bool:
        """Confirm if overlay can be closed."""
        return True
