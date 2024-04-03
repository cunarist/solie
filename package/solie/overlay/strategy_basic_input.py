import re

from PySide6 import QtCore, QtGui, QtWidgets

from solie.common import PACKAGE_PATH, outsource
from solie.utility import Strategy, is_left_version_higher
from solie.widget import BaseOverlay, HorizontalDivider, ask


class StrategyBasicInput(BaseOverlay):
    def __init__(self, strategy: Strategy):
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
        detail_text = QtWidgets.QLabel()
        detail_text.setText("About")
        detail_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
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

        # input
        this_layout = QtWidgets.QFormLayout()
        card_layout.addLayout(this_layout)
        code_name_input = QtWidgets.QLineEdit()
        code_name_input.setText(strategy.code_name)
        this_layout.addRow("Code name", code_name_input)
        readable_name_input = QtWidgets.QLineEdit()
        readable_name_input.setText(strategy.readable_name)
        this_layout.addRow("Readable name", readable_name_input)
        version_input = QtWidgets.QLineEdit()
        version_input.setText(strategy.version)
        this_layout.addRow("Version", version_input)
        description_input = QtWidgets.QTextEdit()
        description_input.setPlainText(strategy.description)
        this_layout.addRow("Description", description_input)
        risk_level_input = QtWidgets.QComboBox()
        iconpath = PACKAGE_PATH / "static" / "icon"
        red_pixmap = QtGui.QPixmap()
        red_pixmap.load(str(iconpath / "traffic_light_red.png"))
        yellow_pixmap = QtGui.QPixmap()
        yellow_pixmap.load(str(iconpath / "traffic_light_yellow.png"))
        green_pixmap = QtGui.QPixmap()
        green_pixmap.load(str(iconpath / "traffic_light_green.png"))
        risk_level_input.addItem(green_pixmap, "Low")
        risk_level_input.addItem(yellow_pixmap, "Middle")
        risk_level_input.addItem(red_pixmap, "High")
        risk_level_input.setCurrentIndex(strategy.risk_level)
        this_layout.addRow("Risk level", risk_level_input)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # explanation
        detail_text = QtWidgets.QLabel()
        detail_text.setText("Simulation")
        detail_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
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

        # input
        this_layout = QtWidgets.QFormLayout()
        card_layout.addLayout(this_layout)
        parallelized_input = QtWidgets.QCheckBox()
        parallelized_input.setChecked(strategy.parallelized_simulation)
        this_layout.addRow("Parallelized", parallelized_input)
        chunk_division_input = QtWidgets.QSpinBox()
        chunk_division_input.setSuffix(" days")
        chunk_division_input.setMinimum(7)
        chunk_division_input.setMaximum(90)
        chunk_division_input.setButtonSymbols(
            QtWidgets.QSpinBox.ButtonSymbols.NoButtons
        )
        chunk_division_input.setValue(strategy.chunk_division)
        this_layout.addRow("Chunk division", chunk_division_input)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # function
        async def job(*args):
            code_name = code_name_input.text()
            if re.fullmatch(r"[A-Z]{6}", code_name):
                strategy.code_name = code_name
            else:
                await ask(
                    "Code name format is wrong.",
                    "You should make the code name with 6 capital letters.",
                    ["Okay"],
                )
                return
            strategy.readable_name = readable_name_input.text()
            version = version_input.text()
            if re.fullmatch(r"[0-9]+\.[0-9]+", version):
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
            strategy.risk_level = risk_level_input.currentIndex()
            strategy.parallelized_simulation = parallelized_input.isChecked()
            strategy.chunk_division = chunk_division_input.value()
            self.done_event.set()

        # confirm button
        confirm_button = QtWidgets.QPushButton("Save and close", card)
        outsource(confirm_button.clicked, job)
        confirm_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # ■■■■■ spacing ■■■■■

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)
