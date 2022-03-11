from PyQt6 import QtWidgets, QtCore


class Gauge(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.is_mouse_over = False
        self.normal_text = ""
        self.lock_text = "🔒"
        self.setFixedHeight(22)

    def mouseReleaseEvent(self, event):  # noqa:N802
        self.clicked.emit()
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):  # noqa:N802
        self.is_mouse_over = True
        super().setText(self.lock_text)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa:N802
        self.is_mouse_over = False
        super().setText(self.normal_text)
        super().leaveEvent(event)

    def setText(self, text):  # noqa:N802
        self.normal_text = text
        if self.is_mouse_over:
            super().setText(self.lock_text)
        else:
            super().setText(self.normal_text)
