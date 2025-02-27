from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget


class BrandLabel(QLabel):
    def __init__(self, parent: QWidget, text="", size=9):
        super().__init__(parent)
        font = QFont("Lexend", size)
        font.setWeight(QFont.Weight.Bold)
        self.setFont(font)
        self.setText(text)
