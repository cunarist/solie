import webbrowser

from PySide6 import QtWidgets, QtGui

from module import core
from module.recipe import outsource
from module.recipe import user_settings
from module.widget.horizontal_divider import HorizontalDivider


class TermsOfAgreement(QtWidgets.QWidget):
    def __init__(self, done_event, payload):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ prepare things ■■■■■

        did_open = False

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QVBoxLayout(self)

        # ■■■■■ spacing ■■■■■

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        full_layout.addItem(spacer)

        # ■■■■■ widgets ■■■■■

        # open button
        def job():
            nonlocal did_open
            webbrowser.open("https://cunarist.com/solie/terms-of-service")
            did_open = True

        this_layout = QtWidgets.QHBoxLayout()
        full_layout.addLayout(this_layout)
        open_button = QtWidgets.QPushButton("Open terms of agreement page", self)
        outsource.do(open_button.clicked, job)
        open_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        open_button.setFixedSize(370, 80)
        this_layout.addWidget(open_button)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        full_layout.addWidget(spacing_text)

        # divider
        this_layout = QtWidgets.QHBoxLayout()
        full_layout.addLayout(this_layout)
        divider = HorizontalDivider(self)
        divider.setFixedWidth(480)
        this_layout.addWidget(divider)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        full_layout.addWidget(spacing_text)

        # confirm button button
        def job():
            if not did_open:
                question = [
                    "It's not read yet",
                    "Read the terms of agreement and agree to proceed.",
                    ["Okay"],
                ]
                core.window.ask(question)
            else:
                user_settings.apply_app_settings({"is_agreement_read": True})
                user_settings.load()
                done_event.set()

        this_layout = QtWidgets.QHBoxLayout()
        full_layout.addLayout(this_layout)
        confirm_button = QtWidgets.QPushButton("Agree", self)
        outsource.do(confirm_button.clicked, job)
        confirm_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        this_layout.addWidget(confirm_button)

        # ■■■■■ spacing ■■■■■

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        full_layout.addItem(spacer)
