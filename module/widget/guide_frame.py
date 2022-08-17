from PySide6 import QtWidgets, QtGui, QtCore


class GuideFrame(QtWidgets.QFrame):
    with open("./static/product_icon_solsol.png", mode="rb") as file:
        image_logo_data = file.read()

    with open("./static/product_text_solsol.png", mode="rb") as file:
        text_logo_data = file.read()

    def __init__(self, total_steps=0):
        super().__init__()

        self.done_steps = 0

        full_layout = QtWidgets.QHBoxLayout()
        self.setLayout(full_layout)

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        full_layout.addItem(spacer)

        central_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(central_layout)

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        central_layout.addItem(spacer)

        this_layout = QtWidgets.QHBoxLayout()
        central_layout.addLayout(this_layout)
        image_logo_pixmap = QtGui.QPixmap()
        image_logo_pixmap.loadFromData(self.image_logo_data)
        image_logo_label = QtWidgets.QLabel("", self)
        image_logo_label.setPixmap(image_logo_pixmap)
        image_logo_label.setScaledContents(True)
        image_logo_label.setFixedSize(80, 80)
        this_layout.addWidget(image_logo_label)
        text_logo_pixmap = QtGui.QPixmap()
        text_logo_pixmap.loadFromData(self.text_logo_data)
        text_logo_label = QtWidgets.QLabel("", self)
        text_logo_label.setPixmap(text_logo_pixmap)
        text_logo_label.setScaledContents(True)
        text_logo_label.setFixedSize(320, 80)
        this_layout.addWidget(text_logo_label)

        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        central_layout.addWidget(spacing_text)

        divider = QtWidgets.QFrame(self)
        divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        divider.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        central_layout.addWidget(divider)

        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        central_layout.addWidget(spacing_text)

        self.guide_label = QtWidgets.QLabel(
            "",
            self,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        central_layout.addWidget(self.guide_label)

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        central_layout.addItem(spacer)

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        full_layout.addItem(spacer)

    def announce(self, guide_text):
        self.guide_label.setText(guide_text)
