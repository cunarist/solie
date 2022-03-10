from PyQt6 import QtWidgets, QtGui


class LogList(QtWidgets.QListWidget):
    def __init__(self, parent):
        super().__init__(parent)
        fixed_width_font = QtGui.QFont("Consolas", 9)
        self.setFont(fixed_width_font)
