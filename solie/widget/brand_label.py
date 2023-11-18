from PySide6 import QtGui, QtWidgets


class BrandLabel(QtWidgets.QLabel):
    def __init__(self, parent, text="", size=9):
        super().__init__(parent)
        font = QtGui.QFont("Lexend", size)
        font.setWeight(QtGui.QFont.Weight.Bold)
        self.setFont(font)
        self.setText(text)
