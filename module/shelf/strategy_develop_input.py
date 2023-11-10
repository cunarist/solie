from PySide6 import QtWidgets, QtCore

from module import core
from module.widget.script_editor import ScriptEditor
from module.recipe import outsource


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

        # function
        def job_as(*args):
            # indicators script
            filepath = "./static/sample_indicators_script.txt"
            with open(filepath, "r", encoding="utf8") as file:
                script = file.read()

            def job_ii(script=script):
                indicators_script_input.setPlainText(script)

            core.window.undertake(job_ii, False)

            # decision script
            filepath = "./static/sample_decision_script.txt"
            with open(filepath, "r", encoding="utf8") as file:
                script = file.read()

            def job(script=script):
                decision_script_input.setPlainText(script)

            core.window.undertake(job, False)

            question = [
                "Sample scripts applied",
                "It is not yet saved. Use it as you want.",
                ["Okay"],
            ]
            core.window.ask(question)

        # sample script button
        fill_button = QtWidgets.QPushButton("Fill with sample", card)
        outsource.do(fill_button.clicked, job_as)
        fill_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(fill_button)

        # function
        def job_ss(*args):
            def job():
                return (
                    indicators_script_input.toPlainText(),
                    decision_script_input.toPlainText(),
                )

            returned: tuple = core.window.undertake(job, True)  # type:ignore
            strategy["indicators_script"] = returned[0]
            strategy["decision_script"] = returned[1]
            done_event.set()

        # confirm button
        confirm_button = QtWidgets.QPushButton("Save and close", card)
        outsource.do(confirm_button.clicked, job_ss)
        confirm_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        card_layout.addItem(spacer)
