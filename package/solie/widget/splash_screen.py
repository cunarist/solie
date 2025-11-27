"""Splash screen widget."""

import aiofiles
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)

from solie.common import PACKAGE_PATH, PACKAGE_VERSION, spawn

from .brand_label import BrandLabel


class SplashScreen(QFrame):
    """Initial loading screen widget."""

    def __init__(self) -> None:
        """Initialize splash screen."""
        super().__init__()

        self.full_layout = QHBoxLayout()
        self.setLayout(self.full_layout)

        spawn(self.fill())

    async def fill(self) -> None:
        """Fill splash screen with branding."""
        full_layout = self.full_layout

        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        full_layout.addItem(spacer)

        central_layout = QVBoxLayout()
        full_layout.addLayout(central_layout)

        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        central_layout.addItem(spacer)

        this_layout = QHBoxLayout()
        central_layout.addLayout(this_layout)
        product_icon_pixmap = QPixmap()
        filepath = PACKAGE_PATH / "static" / "product_icon.png"
        async with aiofiles.open(filepath, mode="rb") as file:
            product_icon_data = await file.read()
        product_icon_pixmap.loadFromData(product_icon_data)
        product_icon_label = QLabel("", self)
        product_icon_label.setPixmap(product_icon_pixmap)
        product_icon_label.setScaledContents(True)
        product_icon_label.setFixedSize(80, 80)
        this_layout.addWidget(product_icon_label)
        spacing_text = QLabel("")
        spacing_text_font = QFont()
        spacing_text_font.setPointSize(8)
        spacing_text.setFont(spacing_text_font)
        this_layout.addWidget(spacing_text)
        title_label = BrandLabel(self, "SOLIE", 48)
        this_layout.addWidget(title_label)
        text = PACKAGE_VERSION
        label = BrandLabel(self, text, 24)
        this_layout.addWidget(label)

        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        central_layout.addItem(spacer)

        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        full_layout.addItem(spacer)
