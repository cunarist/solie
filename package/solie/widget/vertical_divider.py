from PySide6 import QtWidgets


class VerticalDivider(QtWidgets.QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        self.setFixedWidth(2)
