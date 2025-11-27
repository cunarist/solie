"""Gauge button widget with hover effects."""

from typing import override

from PySide6.QtCore import QEvent
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QPushButton, QWidget


class Gauge(QPushButton):
    """Circular gauge button widget."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize gauge button."""
        super().__init__(parent)
        self.is_mouse_over = False
        self.normal_text = ""
        self.lock_text = "🔒"

    @override
    def enterEvent(self, event: QEnterEvent) -> None:
        self.is_mouse_over = True
        self.setFlat(False)
        super().setText(self.lock_text)
        super().enterEvent(event)

    @override
    def leaveEvent(self, event: QEvent) -> None:
        self.is_mouse_over = False
        self.setFlat(True)
        super().setText(self.normal_text)
        super().leaveEvent(event)

    @override
    def setText(self, text: str) -> None:
        self.normal_text = text
        if self.is_mouse_over:
            super().setText(self.lock_text)
        else:
            super().setText(self.normal_text)
