import aiofiles
from PySide6 import QtCore, QtWidgets

import solie
from solie import introduction
from solie.recipe import open_browser, outsource
from solie.widget.script_editor import ScriptEditor
from solie.widget.vertical_divider import VerticalDivider


class StrategyDevelopInput(QtWidgets.QWidget):
    def __init__(self, done_event, payload):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ prepare things ■■■■■

        strategy = payload

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
        indicators_script_input.setPlainText(strategy["indicators_script"])
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
        decision_script_input.setPlainText(strategy["decision_script"])
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

        # API docs button
        async def job_ad(*args):
            url = "https://solie-docs.cunarist.com/making-strategy/"
            open_browser.do(url)

        button = QtWidgets.QPushButton("Show Solie API docs", card)
        outsource.do(button.clicked, job_ad)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(button)

        # Pandas docs button
        async def job_pd(*args):
            url = "https://pandas.pydata.org/docs/reference/index.html"
            open_browser.do(url)

        button = QtWidgets.QPushButton("Show Pandas API docs", card)
        outsource.do(button.clicked, job_pd)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(button)

        # TA docs button
        async def job_td(*args):
            url = "https://github.com/twopirllc/pandas-ta#indicators-by-category"
            open_browser.do(url)

        button = QtWidgets.QPushButton("Show TA API docs", card)
        outsource.do(button.clicked, job_td)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(button)

        # Vertical divider
        divider = VerticalDivider(self)
        card_layout.addWidget(divider)

        # sample script button
        async def job_as(*args):
            # indicators script
            filepath = f"{introduction.PATH}/static/sample_indicators_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                script = await file.read()

            indicators_script_input.setPlainText(script)

            # decision script
            filepath = f"{introduction.PATH}/static/sample_decision_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                script = await file.read()

            decision_script_input.setPlainText(script)

            question = [
                "Sample scripts applied",
                "It is not yet saved. Modify the code as you want.",
                ["Okay"],
            ]
            await solie.window.ask(question)

        button = QtWidgets.QPushButton("Fill with sample", card)
        outsource.do(button.clicked, job_as)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(button)

        # confirm button
        async def job_ss(*args):
            strategy["indicators_script"] = indicators_script_input.toPlainText()
            strategy["decision_script"] = decision_script_input.toPlainText()
            done_event.set()

        button = QtWidgets.QPushButton("Save and close", card)
        outsource.do(button.clicked, job_ss)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(button)

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        card_layout.addItem(spacer)
