import threading

from PySide6 import QtWidgets, QtCore, QtGui

from module.widget.popup_box import PopupBox

# https://stackoverflow.com/questions/67029993/pyqt-creating-a-popup-in-the-window


class OverlapPopup(QtWidgets.QWidget):
    done_event = threading.Event()

    def showEvent(self, event):  # noqa:N802
        # needed for filling the window when resized
        self.setGeometry(self.parent().rect())

    def eventFilter(self, source, event):  # noqa:N802
        # needed for filling the window when resized
        if event.type() == event.Type.Resize:
            self.setGeometry(source.rect())
        return super().eventFilter(source, event)

    def __init__(self, parent, title):
        # ■■■■■ the basic ■■■■■

        super().__init__(parent)

        # ■■■■■ set properties ■■■■■

        # needed for filling the window when resized
        parent.installEventFilter(self)

        # ■■■■■ in case other ask popup exists ■■■■■

        self.done_event.set()
        self.done_event.clear()

        # ■■■■■ prepare answer ■■■■■

        self.answer = 0

        # ■■■■■ full structure ■■■■■

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        self.setAutoFillBackground(True)

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)

        # ■■■■■ visaul box ■■■■■

        # box
        content_box = PopupBox(autoFillBackground=True)
        content_box.setMaximumSize(1600, 1200)
        content_box_layout = QtWidgets.QVBoxLayout(content_box)
        full_layout.addWidget(content_box)

        # line containing the close button
        this_layout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel(title)
        title_label_font = QtGui.QFont()
        title_label_font.setPointSize(12)
        title_label.setFont(title_label_font)
        title_label.setWordWrap(False)
        this_layout.addWidget(title_label)
        widget = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(widget)
        close_button = QtWidgets.QPushButton("✕", content_box)
        close_button_font = QtGui.QFont()
        close_button_font.setPointSize(11)
        close_button.setFont(close_button_font)

        def job():
            self.done_event.set()

        close_button.clicked.connect(job)
        this_layout.addWidget(close_button)
        content_box_layout.addLayout(this_layout)

        # scroll area
        scroll_area = QtWidgets.QScrollArea()
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout()

        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        content_box_layout.addWidget(scroll_area)
        self.scroll_layout = scroll_layout
