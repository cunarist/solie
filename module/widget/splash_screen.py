from PySide6 import QtWidgets, QtGui, QtCore

from module.widget.brand_label import BrandLabel
from module.widget.horizontal_divider import HorizontalDivider
from module import introduction


class SplashScreen(QtWidgets.QFrame):
    def __init__(self):
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
        product_icon_pixmap = QtGui.QPixmap()
        with open("./static/product_icon_solsol.png", mode="rb") as file:
            product_icon_data = file.read()
        product_icon_pixmap.loadFromData(product_icon_data)
        product_icon_label = QtWidgets.QLabel("", self)
        product_icon_label.setPixmap(product_icon_pixmap)
        product_icon_label.setScaledContents(True)
        product_icon_label.setFixedSize(80, 80)
        this_layout.addWidget(product_icon_label)
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(8)
        spacing_text.setFont(spacing_text_font)
        this_layout.addWidget(spacing_text)
        title_label = BrandLabel(self, "SOLSOL", 48)
        this_layout.addWidget(title_label)
        text = introduction.CURRENT_VERSION
        label = BrandLabel(self, text, 24)
        this_layout.addWidget(label)

        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        central_layout.addWidget(spacing_text)

        divider = HorizontalDivider(self)
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
