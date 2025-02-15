import webbrowser

import aiofiles
from PySide6 import QtCore, QtWidgets

from solie.common import PACKAGE_PATH, outsource, spawn_blocking
from solie.utility import SavedStrategy
from solie.widget import BaseOverlay, ScriptEditor, VerticalDivider, ask


class StrategyDevelopInput(BaseOverlay):
    def __init__(self, strategy: SavedStrategy):
        # ■■■■■ the basic ■■■■■

        super().__init__()
        self.strategy = strategy

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
        indicator_script_input = ScriptEditor(self)
        indicator_script_input.setPlainText(strategy.indicator_script)
        column_layout.addWidget(indicator_script_input)
        self.indicator_script_input = indicator_script_input

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
        self.decision_script_input = decision_script_input

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

        # confirm button
        async def job_ss():
            strategy.indicator_script = indicator_script_input.toPlainText()
            strategy.decision_script = decision_script_input.toPlainText()
            self.done_event.set()

        button = QtWidgets.QPushButton("Save and close", card)
        outsource(button.clicked, job_ss)
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

        # sample script button
        async def job_as():
            # indicators script
            filepath = PACKAGE_PATH / "static" / "sample_indicator_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                script = await file.read()

            indicator_script_input.setPlainText(script)

            # decision script
            filepath = PACKAGE_PATH / "static" / "sample_decision_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                script = await file.read()

            decision_script_input.setPlainText(script)

            await ask(
                "Sample scripts applied",
                "It hasn't been saved yet,"
                " feel free to customize the code to your liking.",
                ["Okay"],
            )

        new_action = action_menu.addAction("Apply sample scripts")
        outsource(new_action.triggered, job_as)

        # API docs button
        async def job_ad():
            url = "https://solie-docs.cunarist.com/making-strategy/"
            await spawn_blocking(webbrowser.open, url)

        new_action = action_menu.addAction("Show Solie API docs")
        outsource(new_action.triggered, job_ad)

        # Pandas docs button
        async def job_pd():
            url = "https://pandas.pydata.org/docs/reference/index.html"
            await spawn_blocking(webbrowser.open, url)

        new_action = action_menu.addAction("Show Pandas API docs")
        outsource(new_action.triggered, job_pd)

        # TA docs button
        async def job_td():
            url = "https://github.com/twopirllc/pandas-ta#indicators-by-category"
            await spawn_blocking(webbrowser.open, url)

        new_action = action_menu.addAction("Show TA API docs")
        outsource(new_action.triggered, job_td)

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        card_layout.addItem(spacer)

    async def confirm_closing(self) -> bool:
        strategy = self.strategy

        written_decision = self.decision_script_input.toPlainText()
        is_decision_script_saved = written_decision == strategy.decision_script
        written_indicators = self.indicator_script_input.toPlainText()
        is_indicator_script_saved = written_indicators == strategy.indicator_script
        if is_decision_script_saved and is_indicator_script_saved:
            return True

        should_close = False
        answer = await ask(
            "Scripts are not saved yet",
            "Are you sure you want to exit the editor without saving?",
            ["Cancel", "Exit"],
        )
        if answer == 2:
            should_close = True

        return should_close
