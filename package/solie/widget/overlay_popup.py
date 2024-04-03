# https://stackoverflow.com/questions/67029993/pyqt-creating-a-popup-in-the-window
import asyncio
from typing import TypeVar

from PySide6 import QtCore, QtGui, QtWidgets

from solie.common import outsource

from .popup_box import PopupBox
from .transparent_scroll_area import TransparentScrollArea


class BaseOverlay(QtWidgets.QWidget):
    done_event = asyncio.Event()


W = TypeVar("W", bound=BaseOverlay)


# show an mainpulatable overlap popup
async def overlay(title: str, widget: W, close_button=True) -> W:
    overlay_panel = OverlayPopup(title, widget, close_button)
    overlay_panel.show()

    await widget.done_event.wait()
    overlay_panel.setParent(None)

    return widget


class OverlayPopup(QtWidgets.QWidget):
    installed_window: QtWidgets.QMainWindow

    def showEvent(self, event):  # noqa:N802
        # needed for filling the window when resized
        parent: QtWidgets.QMainWindow = self.parent()  # type:ignore
        self.setGeometry(parent.rect())

    def eventFilter(self, source, event):  # noqa:N802
        # needed for filling the window when resized
        if event.type() == event.Type.Resize:
            self.setGeometry(source.rect())
        return super().eventFilter(source, event)

    @classmethod
    def install_window(cls, window: QtWidgets.QMainWindow):
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

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        self.setAutoFillBackground(True)

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)

        # ■■■■■ visaul box ■■■■■

        # box
        content_box = PopupBox()
        content_box.setAutoFillBackground(True)
        content_box.setMaximumSize(1600, 1200)
        content_box_layout = QtWidgets.QVBoxLayout(content_box)
        full_layout.addWidget(content_box)

        # line containing the title and close button
        this_layout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel(title)
        title_label_font = QtGui.QFont()
        title_label_font.setPointSize(12)
        title_label.setFont(title_label_font)
        title_label.setWordWrap(False)
        this_layout.addWidget(title_label)
        top_widget = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(top_widget)
        if close_button:
            close_button_widget = QtWidgets.QPushButton("✕", content_box)
            close_button_font = QtGui.QFont()
            close_button_font.setPointSize(11)
            close_button_widget.setFont(close_button_font)

            async def job():
                widget.done_event.set()

            outsource(close_button_widget.clicked, job)
            this_layout.addWidget(close_button_widget)
        content_box_layout.addLayout(this_layout)

        # scroll area
        scroll_area = TransparentScrollArea()

        scroll_area.setWidget(widget)
        scroll_area.setWidgetResizable(True)

        content_box_layout.addWidget(scroll_area)
