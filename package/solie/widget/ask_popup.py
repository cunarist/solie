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
    def showEvent(self, event: QShowEvent) -> None:
        # needed for filling the window when resized
        parent: QMainWindow = self.parent()  # type:ignore
        self.setGeometry(parent.rect())

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not isinstance(watched, QWidget):
            raise NotImplementedError
        # needed for filling the window when resized
        if event.type() == event.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)

    @classmethod
    def install_window(cls, window: QMainWindow) -> None:
        cls.installed_window = window

    def __init__(
        self,
        main_text: str,
        detail_text: str,
        options: list[str],
    ) -> None:
        super().__init__(self.installed_window)

        # needed for filling the window when resized
        self.installed_window.installEventFilter(self)

        # Reset done event
        self.done_event.set()
        self.done_event.clear()

        self.answer = 0

        # Setup widget attributes
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAutoFillBackground(True)

        # Create main layout
        full_layout = QHBoxLayout(self)

        # Create content box
        content_box = self._create_content_box()
        content_box_layout = QVBoxLayout(content_box)
        full_layout.addWidget(content_box)

        # Setup UI components
        self._add_close_button(content_box, content_box_layout)
        self._add_text_content(content_box_layout, main_text, detail_text)
        self._add_option_buttons(content_box, content_box_layout, options)

    def _create_content_box(self) -> PopupBox:
        """Create and configure the content box."""
        content_box = PopupBox()
        content_box.setAutoFillBackground(True)
        content_box.setFixedSize(520, 520)
        return content_box

    def _add_close_button(self, content_box: PopupBox, layout: QVBoxLayout) -> None:
        """Add close button to the top right."""
        this_layout = QHBoxLayout()
        widget = QSpacerItem(
            0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        this_layout.addItem(widget)

        close_button = QPushButton("✕", content_box)
        close_button_font = QFont()
        close_button_font.setPointSize(11)
        close_button.setFont(close_button_font)

        async def job_de() -> None:
            self.done_event.set()

        outsource(close_button.clicked, job_de)
        this_layout.addWidget(close_button)
        layout.addLayout(this_layout)

    def _add_text_content(
        self, layout: QVBoxLayout, main_text: str, detail_text: str
    ) -> None:
        """Add main and detail text widgets."""
        # Top spacer
        widget = QSpacerItem(
            0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        layout.addItem(widget)

        # Main text
        main_text_widget = QLabel()
        main_text_widget.setText(main_text)
        main_text_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_text_font = QFont()
        main_text_font.setPointSize(12)
        main_text_widget.setFont(main_text_font)
        main_text_widget.setWordWrap(True)
        layout.addWidget(main_text_widget)

        # Spacing
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        layout.addWidget(spacing_text)

        # Detail text
        detail_text_widget = QLabel()
        detail_text_widget.setText(detail_text)
        detail_text_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_text_widget.setWordWrap(True)
        layout.addWidget(detail_text_widget)

        # Bottom spacer
        widget = QSpacerItem(
            0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        layout.addItem(widget)

    def _add_option_buttons(
        self, content_box: PopupBox, layout: QVBoxLayout, options: list[str]
    ) -> None:
        """Add option buttons."""
        this_layout = QHBoxLayout()
        for turn, option in enumerate(options):
            option_button = QPushButton(option, content_box)

            async def job(answer=turn + 1) -> None:
                self.answer = answer
                self.done_event.set()

            outsource(option_button.clicked, job)
            option_button.setMaximumWidth(240)
            this_layout.addWidget(option_button)

        layout.addLayout(this_layout)
