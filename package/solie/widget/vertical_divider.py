"""Vertical divider widget."""

from PySide6.QtWidgets import QFrame, QWidget


class VerticalDivider(QFrame):
    """Vertical line divider widget."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize vertical divider."""
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFixedWidth(2)
