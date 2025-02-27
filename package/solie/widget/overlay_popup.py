# https://stackoverflow.com/questions/67029993/pyqt-creating-a-popup-in-the-window
from asyncio import Event
from typing import TypeVar

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
from typing_extensions import override

from solie.common import outsource

from .popup_box import PopupBox
from .transparent_scroll_area import TransparentScrollArea


class BaseOverlay(QWidget):
    done_event = Event()

    async def confirm_closing(self) -> bool:
        return True


W = TypeVar("W", bound=BaseOverlay)


# show an mainpulatable overlap popup
async def overlay(title: str, widget: W, close_button=True) -> W:
    overlay_panel = OverlayPopup(title, widget, close_button)
    overlay_panel.show()

    await widget.done_event.wait()
    overlay_panel.setParent(None)

    return widget


class OverlayPopup(QWidget):
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
        title: str,
        widget: BaseOverlay,
        close_button: bool,
    ):
        # ■■■■■ the basic ■■■■■

        super().__init__(self.installed_window)

        # ■■■■■ set properties ■■■■■

        # needed for filling the window when resized
        self.installed_window.installEventFilter(self)

        # ■■■■■ in case other overlay popup exists ■■■■■

        widget.done_event.set()
        widget.done_event.clear()

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
        content_box.setMaximumSize(1600, 1200)
        content_box_layout = QVBoxLayout(content_box)
        full_layout.addWidget(content_box)

        # line containing the title and close button
        this_layout = QHBoxLayout()
        title_label = QLabel(title)
        title_label_font = QFont()
        title_label_font.setPointSize(12)
        title_label.setFont(title_label_font)
        title_label.setWordWrap(False)
        this_layout.addWidget(title_label)
        top_widget = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(top_widget)
        if close_button:
            close_button_widget = QPushButton("✕", content_box)
            close_button_font = QFont()
            close_button_font.setPointSize(11)
            close_button_widget.setFont(close_button_font)

            async def job():
                should_close = await widget.confirm_closing()
                if should_close:
                    widget.done_event.set()

            outsource(close_button_widget.clicked, job)
            this_layout.addWidget(close_button_widget)
        content_box_layout.addLayout(this_layout)

        # scroll area
        scroll_area = TransparentScrollArea()

        scroll_area.setWidget(widget)
        scroll_area.setWidgetResizable(True)

        content_box_layout.addWidget(scroll_area)
