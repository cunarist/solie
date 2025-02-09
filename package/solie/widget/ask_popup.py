import asyncio

from PySide6 import QtCore, QtGui, QtWidgets
from typing_extensions import override

from solie.common import outsource

from .popup_box import PopupBox

# https://stackoverflow.com/questions/67029993/pyqt-creating-a-popup-in-the-window


# show an ask popup and blocks the stack
async def ask(main_text: str, detail_text: str, options: list[str]) -> int:
    ask_popup = AskPopup(main_text, detail_text, options)
    ask_popup.show()

    await ask_popup.done_event.wait()
    ask_popup.setParent(None)

    return ask_popup.answer


class AskPopup(QtWidgets.QWidget):
    done_event = asyncio.Event()
    installed_window: QtWidgets.QMainWindow

    @override
    def showEvent(self, event):
        # needed for filling the window when resized
        parent: QtWidgets.QMainWindow = self.parent()  # type:ignore
        self.setGeometry(parent.rect())

    @override
    def eventFilter(self, watched, event):
        if not isinstance(watched, QtWidgets.QWidget):
            raise NotImplementedError
        # needed for filling the window when resized
        if event.type() == event.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)

    @classmethod
    def install_window(cls, window: QtWidgets.QMainWindow):
        cls.installed_window = window

    def __init__(
        self,
        main_text: str,
        detail_text: str,
        options: list[str],
    ):
        # ■■■■■ the basic ■■■■■

        super().__init__(self.installed_window)

        # ■■■■■ set properties ■■■■■

        # needed for filling the window when resized
        self.installed_window.installEventFilter(self)

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

        outsource(close_button.clicked, job_de)
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
        main_text_widget = QtWidgets.QLabel()
        main_text_widget.setText(main_text)
        main_text_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        main_text_font = QtGui.QFont()
        main_text_font.setPointSize(12)
        main_text_widget.setFont(main_text_font)
        main_text_widget.setWordWrap(True)
        content_box_layout.addWidget(main_text_widget)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        content_box_layout.addWidget(spacing_text)

        # explanation
        detail_text_widget = QtWidgets.QLabel()
        detail_text_widget.setText(detail_text)
        detail_text_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        detail_text_widget.setWordWrap(True)
        content_box_layout.addWidget(detail_text_widget)

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
        for turn, option in enumerate(options):
            option_button = QtWidgets.QPushButton(option, content_box)

            async def job(answer=turn + 1):
                self.answer = answer
                self.done_event.set()

            outsource(option_button.clicked, job)
            option_button.setMaximumWidth(240)
            this_layout.addWidget(option_button)

        content_box_layout.addLayout(this_layout)
