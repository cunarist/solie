from PySide6.QtCore import QEvent
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QPushButton, QWidget
from typing_extensions import override


class Gauge(QPushButton):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.is_mouse_over = False
        self.normal_text = ""
        self.lock_text = "🔒"

    @override
    def enterEvent(self, event: QEnterEvent):
        self.is_mouse_over = True
        self.setFlat(False)
        super().setText(self.lock_text)
        super().enterEvent(event)

    @override
    def leaveEvent(self, event: QEvent):
        self.is_mouse_over = False
        self.setFlat(True)
        super().setText(self.normal_text)
        super().leaveEvent(event)

    @override
    def setText(self, text: str):
        self.normal_text = text
        if self.is_mouse_over:
            super().setText(self.lock_text)
        else:
            super().setText(self.normal_text)
