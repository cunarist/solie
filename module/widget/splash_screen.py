import asyncio

from PySide6 import QtWidgets, QtGui
import aiofiles

from module.widget.brand_label import BrandLabel
from module import introduction


class SplashScreen(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()

        self.full_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.full_layout)

        asyncio.create_task(self.fill())

    async def fill(self):
        full_layout = self.full_layout

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
        async with aiofiles.open("./static/product_icon.png", mode="rb") as file:
            product_icon_data = await file.read()
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
        title_label = BrandLabel(self, "SOLIE", 48)
        this_layout.addWidget(title_label)
        text = introduction.CURRENT_VERSION
        label = BrandLabel(self, text, 24)
        this_layout.addWidget(label)

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
