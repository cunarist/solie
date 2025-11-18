from PySide6.QtWidgets import QFrame, QWidget


class VerticalDivider(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFixedWidth(2)
