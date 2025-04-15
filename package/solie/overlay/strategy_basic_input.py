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
from solie.utility import RiskLevel, Strategy, is_left_version_higher
from solie.widget import HorizontalDivider, ask


class StrategyBasicInput:
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
        detail_text.setText("About")
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

        # input
        this_layout = QFormLayout()
        card_layout.addLayout(this_layout)
        code_name_input = QLineEdit()
        code_name_input.setText(strategy.code_name)
        this_layout.addRow("Code name", code_name_input)
        readable_name_input = QLineEdit()
        readable_name_input.setText(strategy.readable_name)
        this_layout.addRow("Readable name", readable_name_input)
        version_input = QLineEdit()
        version_input.setText(strategy.version)
        this_layout.addRow("Version", version_input)
        description_input = QTextEdit()
        description_input.setPlainText(strategy.description)
        this_layout.addRow("Description", description_input)
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
        this_layout.addRow("Risk level", risk_level_input)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # explanation
        detail_text = QLabel()
        detail_text.setText("Simulation")
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

        # input
        this_layout = QFormLayout()
        card_layout.addLayout(this_layout)
        parallelized_input = QCheckBox()
        parallelized_input.setChecked(bool(strategy.parallel_simulation_chunk_days))
        this_layout.addRow("Parallelized", parallelized_input)
        chunk_division_input = QSpinBox()
        chunk_division_input.setSuffix(" days")
        chunk_division_input.setMinimum(7)
        chunk_division_input.setMaximum(90)
        chunk_division_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        chunk_division_input.setValue(strategy.parallel_simulation_chunk_days or 0)
        this_layout.addRow("Chunk division", chunk_division_input)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QGroupBox()
        card.setFixedWidth(720)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # function
        async def job():
            strategy.readable_name = readable_name_input.text()
            version = version_input.text()
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
            strategy.description = description_input.toPlainText()
            strategy.risk_level = RiskLevel(risk_level_input.currentIndex())
            parallel = parallelized_input.isChecked()
            parallel_chunk_days = chunk_division_input.value() if parallel else None
            strategy.parallel_simulation_chunk_days = parallel_chunk_days
            self.done_event.set()

        # confirm button
        confirm_button = QPushButton("Save and close", card)
        outsource(confirm_button.clicked, job)
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
