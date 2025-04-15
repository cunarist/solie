from asyncio import Event

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LongTextView:
    done_event = Event()
    result = None

    def __init__(self, long_text: str):
        # ■■■■■ the basic ■■■■■

        super().__init__()
        self.widget = QWidget()

        # ■■■■■ full layout ■■■■■

        full_layout = QVBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        label = QLabel(long_text)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cards_layout.addWidget(label)

    async def confirm_closing(self) -> bool:
        return True
