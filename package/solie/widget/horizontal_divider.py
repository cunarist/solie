"""Horizontal divider widget."""

from PySide6.QtWidgets import QFrame, QWidget


class HorizontalDivider(QFrame):
    """Horizontal line divider widget."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize horizontal divider."""
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(2)
