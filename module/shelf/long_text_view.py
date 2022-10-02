from PySide6 import QtWidgets, QtGui


class LongTextView(QtWidgets.QWidget):
    def __init__(self, done_event, payload):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        label = QtWidgets.QLabel(payload[0])
        fixed_width_font = QtGui.QFont("Consolas", 9)
        label.setFont(fixed_width_font)
        cards_layout.addWidget(label)
