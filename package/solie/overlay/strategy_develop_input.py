import webbrowser

import aiofiles
from PySide6 import QtCore, QtWidgets

import solie
from solie.definition.structs import Strategy
from solie.parallel import go
from solie.utility import outsource
from solie.widget.script_editor import ScriptEditor
from solie.widget.vertical_divider import VerticalDivider

from .base_overlay import BaseOverlay


class StrategyDevelopInput(BaseOverlay):
    def __init__(self, strategy: Strategy):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QVBoxLayout(self)

        # ■■■■■ script editors ■■■■■

        this_layout = QtWidgets.QHBoxLayout()
        full_layout.addLayout(this_layout)

        # column layout
        column_layout = QtWidgets.QVBoxLayout()
        this_layout.addLayout(column_layout)

        # title
        detail_text = QtWidgets.QLabel()
        detail_text.setText("Indicators script")
        detail_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        column_layout.addWidget(detail_text)

        # input
        indicators_script_input = ScriptEditor(self)
        indicators_script_input.setPlainText(strategy.indicators_script)
        column_layout.addWidget(indicators_script_input)

        # column layout
        column_layout = QtWidgets.QVBoxLayout()
        this_layout.addLayout(column_layout)

        # title
        detail_text = QtWidgets.QLabel()
        detail_text.setText("Decision script")
        detail_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        column_layout.addWidget(detail_text)

        # input
        decision_script_input = ScriptEditor(self)
        decision_script_input.setPlainText(strategy.decision_script)
        column_layout.addWidget(decision_script_input)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox()
        card_layout = QtWidgets.QHBoxLayout(card)
        full_layout.addWidget(card)

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        card_layout.addItem(spacer)

        # sample script button
        async def job_as(*args):
            # indicators script
            filepath = solie.info.PATH / "static" / "sample_indicators_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                script = await file.read()

            indicators_script_input.setPlainText(script)

            # decision script
            filepath = solie.info.PATH / "static" / "sample_decision_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                script = await file.read()

            decision_script_input.setPlainText(script)

            await solie.window.ask(
                "Sample scripts applied",
                "It is not yet saved. Modify the code as you want.",
                ["Okay"],
            )

        button = QtWidgets.QPushButton("Fill with sample", card)
        outsource.outsource(button.clicked, job_as)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(button)

        # confirm button
        async def job_ss(*args):
            strategy.indicators_script = indicators_script_input.toPlainText()
            strategy.decision_script = decision_script_input.toPlainText()
            self.done_event.set()

        button = QtWidgets.QPushButton("Save and close", card)
        outsource.outsource(button.clicked, job_ss)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(button)

        # Vertical divider
        divider = VerticalDivider(self)
        card_layout.addWidget(divider)

        # action menu
        action_menu = QtWidgets.QMenu(self)
        action_button = QtWidgets.QPushButton()
        action_button.setText("☰")
        action_button.setMenu(action_menu)
        card_layout.addWidget(action_button)

        # API docs button
        async def job_ad(*args):
            url = "https://solie-docs.cunarist.com/making-strategy/"
            await go(webbrowser.open, url)

        new_action = action_menu.addAction("Show Solie API docs")
        outsource.outsource(new_action.triggered, job_ad)

        # Pandas docs button
        async def job_pd(*args):
            url = "https://pandas.pydata.org/docs/reference/index.html"
            await go(webbrowser.open, url)

        new_action = action_menu.addAction("Show Pandas API docs")
        outsource.outsource(new_action.triggered, job_pd)

        # TA docs button
        async def job_td(*args):
            url = "https://github.com/twopirllc/pandas-ta#indicators-by-category"
            await go(webbrowser.open, url)

        new_action = action_menu.addAction("Show TA API docs")
        outsource.outsource(new_action.triggered, job_td)

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        card_layout.addItem(spacer)
