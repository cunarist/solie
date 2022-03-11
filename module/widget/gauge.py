from PyQt6 import QtWidgets, QtCore


class Gauge(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.is_mouse_over = False
        self.normal_text = ""
        self.guide_text = "🔒"

    def mousePressEvent(self, event):  # noqa:N802
        self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):  # noqa:N802
        self.is_mouse_over = True
        super().setText(self.guide_text)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa:N802
        self.is_mouse_over = False
        super().setText(self.normal_text)
        super().leaveEvent(event)

    def setText(self, text):  # noqa:N802
        self.normal_text = text
        if self.is_mouse_over:
            super().setText(self.guide_text)
        else:
            super().setText(self.normal_text)
