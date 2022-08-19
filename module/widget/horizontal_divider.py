from PySide6 import QtWidgets


class HorizontalDivider(QtWidgets.QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.setFixedHeight(2)
