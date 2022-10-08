from PySide6 import QtWidgets, QtGui

from module import core
from module import thread_toss
from module.shelf.long_text_view import LongTextView


class LogList(QtWidgets.QListWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.fixed_width_font = QtGui.QFont("Consolas", 9)
        self.setFont(self.fixed_width_font)
        self.itemClicked.connect(self.show_fulltext)

    def addItem(self, summarization, log_content):  # noqa:N802
        maximum_item_limit = 1024

        new_item = QtWidgets.QListWidgetItem(self)
        new_item.log_content = log_content
        new_item.setText(summarization)

        super().addItem(new_item)

        index_count = self.count()

        if index_count > maximum_item_limit:
            remove_count = index_count - maximum_item_limit
            for _ in range(remove_count):
                self.takeItem(0)

    def show_fulltext(self, *args, **kwargs):
        selected_index = self.currentRow()

        selected_item = self.item(selected_index)
        text = selected_item.log_content

        def job():
            formation = ["This is the full log", LongTextView, True, [text]]
            core.window.overlap(formation)

        thread_toss.apply_async(job)
