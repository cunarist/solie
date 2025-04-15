from asyncio import Event

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from solie.common import outsource

from .overlay_popup import overlay


class LogOverlay:
    title = "This is the full log"
    close_button = True
    done_event = Event()

    def __init__(self, log_content: str):
        # ■■■■■ the basic ■■■■■

        super().__init__()
        self.widget = QWidget()
        self.result = None

        # ■■■■■ full layout ■■■■■

        full_layout = QVBoxLayout(self.widget)
        cards_layout = QVBoxLayout()
        full_layout.addLayout(cards_layout)

        label = QLabel(log_content)
        fixed_width_font = QFont("Source Code Pro", 9)
        label.setFont(fixed_width_font)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cards_layout.addWidget(label)

    async def confirm_closing(self) -> bool:
        return True


class LogList(QListWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.fixed_width_font = QFont("Source Code Pro", 9)
        self.setFont(self.fixed_width_font)
        outsource(self.itemClicked, self.show_fulltext)

    def add_item(self, summarization: str, log_content: str):
        maximum_item_limit = 1024

        new_item = QListWidgetItem(self)
        new_item.setText(summarization)
        new_item.setData(Qt.ItemDataRole.UserRole, log_content)

        super().addItem(new_item)

        index_count = self.count()

        if index_count > maximum_item_limit:
            remove_count = index_count - maximum_item_limit
            for _ in range(remove_count):
                self.takeItem(0)

    async def show_fulltext(self):
        selected_index = self.currentRow()

        selected_item = self.item(selected_index)
        text = selected_item.data(Qt.ItemDataRole.UserRole)

        await overlay(LogOverlay(text))
