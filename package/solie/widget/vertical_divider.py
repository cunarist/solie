from PySide6.QtWidgets import QFrame


class VerticalDivider(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFixedWidth(2)
