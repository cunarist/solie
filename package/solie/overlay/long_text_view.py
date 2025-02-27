from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout

from solie.widget import BaseOverlay


class LongTextView(BaseOverlay):
    def __init__(self, long_text: str):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ full layout ■■■■■

        full_layout = QVBoxLayout(self)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        label = QLabel(long_text)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cards_layout.addWidget(label)
