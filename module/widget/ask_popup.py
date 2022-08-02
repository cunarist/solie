import threading

from PyQt6 import QtWidgets, QtCore, QtGui

from module.widget.ask_popup_content import AskPopupContent

# https://stackoverflow.com/questions/67029993/pyqt-creating-a-popup-in-the-window


class AskPopup(QtWidgets.QWidget):

    done_event = threading.Event()

    def showEvent(self, event):  # noqa:N802
        # needed for filling the window when resized
        self.setGeometry(self.parent().rect())

    def eventFilter(self, source, event):  # noqa:N802
        # needed for filling the window when resized
        if event.type() == event.Type.Resize:
            self.setGeometry(source.rect())
        return super().eventFilter(source, event)

    def __init__(self, root, question):

        # ■■■■■ the basic ■■■■■

        super().__init__(root)

        # ■■■■■ set properties ■■■■■

        # needed for filling the window when resized
        root.installEventFilter(self)

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
        content_box = AskPopupContent(autoFillBackground=True)
        content_box_layout = QtWidgets.QVBoxLayout(content_box)
        full_layout.addWidget(content_box)

        # line containing the close button
        this_layout = QtWidgets.QHBoxLayout()
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

        # spacing
        widget = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        content_box_layout.addItem(widget)

        # title
        main_text = QtWidgets.QLabel(
            question[0],
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        main_text_font = QtGui.QFont()
        main_text_font.setPointSize(12)
        main_text.setFont(main_text_font)
        main_text.setWordWrap(True)
        content_box_layout.addWidget(main_text)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        content_box_layout.addWidget(spacing_text)

        # explanation
        detail_text = QtWidgets.QLabel(
            question[1],
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        detail_text.setWordWrap(True)
        content_box_layout.addWidget(detail_text)

        # spacing
        widget = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        content_box_layout.addItem(widget)

        # line including selection buttons
        if question[3]:
            this_layout = QtWidgets.QVBoxLayout()
        else:
            this_layout = QtWidgets.QHBoxLayout()
        for turn, option in enumerate(question[2]):
            option_button = QtWidgets.QPushButton(option, content_box)

            def job(_, answer=turn + 1):
                self.answer = answer
                self.done_event.set()

            option_button.clicked.connect(job)
            if not question[3]:
                option_button.setMaximumWidth(240)
            this_layout.addWidget(option_button)

        content_box_layout.addLayout(this_layout)
