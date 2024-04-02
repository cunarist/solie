from PySide6 import QtCore, QtGui, QtWidgets

from .base import BaseOverlay


class LongTextView(BaseOverlay):
    def __init__(self, long_text: str):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QVBoxLayout(self)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        label = QtWidgets.QLabel(long_text)
        fixed_width_font = QtGui.QFont("Source Code Pro", 9)
        label.setFont(fixed_width_font)
        label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        cards_layout.addWidget(label)
