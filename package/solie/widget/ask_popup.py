import asyncio
from dataclasses import dataclass

from PySide6 import QtCore, QtGui, QtWidgets

from solie.utility import outsource
from solie.widget.popup_box import PopupBox

# https://stackoverflow.com/questions/67029993/pyqt-creating-a-popup-in-the-window


@dataclass
class Question:
    main_text: str
    detail_text: str
    options: list[str]


class AskPopup(QtWidgets.QWidget):
    done_event = asyncio.Event()

    def showEvent(self, event):  # noqa:N802
        # needed for filling the window when resized
        parent: QtWidgets.QMainWindow = self.parent()  # type:ignore
        self.setGeometry(parent.rect())

    def eventFilter(self, source, event):  # noqa:N802
        # needed for filling the window when resized
        if event.type() == event.Type.Resize:
            self.setGeometry(source.rect())
        return super().eventFilter(source, event)

    def __init__(self, parent: QtWidgets.QMainWindow, question: Question):
        # ■■■■■ the basic ■■■■■

        super().__init__(parent)

        # ■■■■■ set properties ■■■■■

        # needed for filling the window when resized
        parent.installEventFilter(self)

        # ■■■■■ in case other ask popup exists ■■■■■

        self.done_event.set()
        self.done_event.clear()

        # ■■■■■ prepare answer ■■■■■

        self.answer = 0

        # ■■■■■ full structure ■■■■■

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        self.setAutoFillBackground(True)

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)

        # ■■■■■ visaul box ■■■■■

        # box
        content_box = PopupBox()
        content_box.setAutoFillBackground(True)
        content_box.setFixedSize(520, 520)
        content_box_layout = QtWidgets.QVBoxLayout(content_box)
        full_layout.addWidget(content_box)

        # line containing the close button
        this_layout = QtWidgets.QHBoxLayout()
        widget = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(widget)
        close_button = QtWidgets.QPushButton("✕", content_box)
        close_button_font = QtGui.QFont()
        close_button_font.setPointSize(11)
        close_button.setFont(close_button_font)

        async def job_de():
            self.done_event.set()

        outsource.do(close_button.clicked, job_de)
        this_layout.addWidget(close_button)
        content_box_layout.addLayout(this_layout)

        # spacing
        widget = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        content_box_layout.addItem(widget)

        # title
        main_text = QtWidgets.QLabel()
        main_text.setText(question.main_text)
        main_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        main_text_font = QtGui.QFont()
        main_text_font.setPointSize(12)
        main_text.setFont(main_text_font)
        main_text.setWordWrap(True)
        content_box_layout.addWidget(main_text)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        content_box_layout.addWidget(spacing_text)

        # explanation
        detail_text = QtWidgets.QLabel()
        detail_text.setText(question.detail_text)
        detail_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        detail_text.setWordWrap(True)
        content_box_layout.addWidget(detail_text)

        # spacing
        widget = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        content_box_layout.addItem(widget)

        # line including selection buttons
        this_layout = QtWidgets.QHBoxLayout()
        for turn, option in enumerate(question.options):
            option_button = QtWidgets.QPushButton(option, content_box)

            async def job(answer=turn + 1, *args, **kwargs):
                self.answer = answer
                self.done_event.set()

            outsource.do(option_button.clicked, job)
            option_button.setMaximumWidth(240)
            this_layout.addWidget(option_button)

        content_box_layout.addLayout(this_layout)
