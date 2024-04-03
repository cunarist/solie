from PySide6 import QtCore, QtGui, QtWidgets

from solie.common import outsource
from solie.overlay import LongTextView

from .overlay_panel import overlay


class LogList(QtWidgets.QListWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.fixed_width_font = QtGui.QFont("Source Code Pro", 9)
        self.setFont(self.fixed_width_font)
        outsource(self.itemClicked, self.show_fulltext)

    def add_item(self, summarization: str, log_content: str):
        maximum_item_limit = 1024

        new_item = QtWidgets.QListWidgetItem(self)
        new_item.setText(summarization)
        new_item.setData(QtCore.Qt.ItemDataRole.UserRole, log_content)

        super().addItem(new_item)

        index_count = self.count()

        if index_count > maximum_item_limit:
            remove_count = index_count - maximum_item_limit
            for _ in range(remove_count):
                self.takeItem(0)

    async def show_fulltext(self, *args, **kwargs):
        selected_index = self.currentRow()

        selected_item = self.item(selected_index)
        text = selected_item.data(QtCore.Qt.ItemDataRole.UserRole)

        await overlay(
            "This is the full log",
            LongTextView(text),
        )
