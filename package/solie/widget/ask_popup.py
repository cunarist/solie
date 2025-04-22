from asyncio import Event
from typing import override

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFont, QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

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


class AskPopup(QWidget):
    done_event = Event()
    result = None
    installed_window: QMainWindow

    @override
    def showEvent(self, event: QShowEvent):
        # needed for filling the window when resized
        parent: QMainWindow = self.parent()  # type:ignore
        self.setGeometry(parent.rect())

    @override
    def eventFilter(self, watched: QObject, event: QEvent):
        if not isinstance(watched, QWidget):
            raise NotImplementedError
        # needed for filling the window when resized
        if event.type() == event.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)

    @classmethod
    def install_window(cls, window: QMainWindow):
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

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAutoFillBackground(True)

        # ■■■■■ full layout ■■■■■

        full_layout = QHBoxLayout(self)

        # ■■■■■ visaul box ■■■■■

        # box
        content_box = PopupBox()
        content_box.setAutoFillBackground(True)
        content_box.setFixedSize(520, 520)
        content_box_layout = QVBoxLayout(content_box)
        full_layout.addWidget(content_box)

        # line containing the close button
        this_layout = QHBoxLayout()
        widget = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(widget)
        close_button = QPushButton("✕", content_box)
        close_button_font = QFont()
        close_button_font.setPointSize(11)
        close_button.setFont(close_button_font)

        async def job_de():
            self.done_event.set()

        outsource(close_button.clicked, job_de)
        this_layout.addWidget(close_button)
        content_box_layout.addLayout(this_layout)

        # spacing
        widget = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        content_box_layout.addItem(widget)

        # title
        main_text_widget = QLabel()
        main_text_widget.setText(main_text)
        main_text_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_text_font = QFont()
        main_text_font.setPointSize(12)
        main_text_widget.setFont(main_text_font)
        main_text_widget.setWordWrap(True)
        content_box_layout.addWidget(main_text_widget)

        # spacing
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        content_box_layout.addWidget(spacing_text)

        # explanation
        detail_text_widget = QLabel()
        detail_text_widget.setText(detail_text)
        detail_text_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text_widget.setWordWrap(True)
        content_box_layout.addWidget(detail_text_widget)

        # spacing
        widget = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        content_box_layout.addItem(widget)

        # line including selection buttons
        this_layout = QHBoxLayout()
        for turn, option in enumerate(options):
            option_button = QPushButton(option, content_box)

            async def job(answer=turn + 1):
                self.answer = answer
                self.done_event.set()

            outsource(option_button.clicked, job)
            option_button.setMaximumWidth(240)
            this_layout.addWidget(option_button)

        content_box_layout.addLayout(this_layout)
