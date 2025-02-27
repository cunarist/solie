from PySide6.QtWidgets import QFrame


class HorizontalDivider(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(2)
