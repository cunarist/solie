"""Styled brand label widget."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget


class BrandLabel(QLabel):
    """Label with custom brand styling."""

    def __init__(self, parent: QWidget, text: str = "", size: int = 9) -> None:
        """Initialize brand label."""
        super().__init__(parent)
        font = QFont("Lexend", size)
        font.setWeight(QFont.Weight.Bold)
        self.setFont(font)
        self.setText(text)
