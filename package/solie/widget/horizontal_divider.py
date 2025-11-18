from PySide6.QtWidgets import QFrame, QWidget


class HorizontalDivider(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(2)
