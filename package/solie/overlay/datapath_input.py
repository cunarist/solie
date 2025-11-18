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
from solie.widget import HorizontalDivider, ask


class DatapathInput:
    title = "Choose your data folder"
    close_button = False
    done_event = Event()

    def __init__(self) -> None:
        # ■■■■■ the basic ■■■■■

        super().__init__()
        self.widget = QWidget()
        self.result: Path

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
        detail_text.setText("All the data that Solie produces will go in this folder.")
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

        # chosen folder label
        folder_label = QLabel()
        folder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        folder_label.setWordWrap(True)
        card_layout.addWidget(folder_label)

        # spacing
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        datapath: Path | None = None

        async def job_dp() -> None:
            nonlocal datapath
            str_path = await spawn_blocking(directory, title="Data folder")
            datapath = Path(str_path)
            folder_label.setText(str(datapath))

        # choose button
        this_layout = QHBoxLayout()
        card_layout.addLayout(this_layout)
        choose_button = QPushButton("Choose folder", card)
        outsource(choose_button.clicked, job_dp)
        choose_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        this_layout.addWidget(choose_button)

        # ■■■■■ a card ■■■■■

        async def job_ac() -> None:
            if datapath is None:
                await ask(
                    "Data folder is not chosen",
                    "Choose your data folder first.",
                    ["Okay"],
                )
            else:
                self.result = datapath
                self.done_event.set()

        # card structure
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # confirm button
        confirm_button = QPushButton("Okay", card)
        outsource(confirm_button.clicked, job_ac)
        confirm_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

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
