from asyncio import Event

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LongTextView:
    title = "This is the raw account state object"
    close_button = True
    done_event = Event()

    def __init__(self, long_text: str):
        # ■■■■■ the basic ■■■■■

        super().__init__()
        self.widget = QWidget()
        self.result = None

        # ■■■■■ full layout ■■■■■

        full_layout = QVBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        label = QLabel(long_text)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cards_layout.addWidget(label)

    async def confirm_closing(self) -> bool:
        return True
