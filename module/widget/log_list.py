from PySide6 import QtWidgets, QtGui

from module import core
from module import thread_toss
from module.shelf.full_log_view import FullLogView


class LogList(QtWidgets.QListWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.fixed_width_font = QtGui.QFont("Consolas", 9)
        self.setFont(self.fixed_width_font)
        self.itemClicked.connect(self.show_fulltext)

    def addItem(self, fulltext):  # noqa:N802
        maximum_item_limit = 1024

        new_item = QtWidgets.QListWidgetItem(self)
        new_item.fulltext = fulltext
        new_item.setText(fulltext.split("\n")[0])

        super().addItem(new_item)

        index_count = self.count()

        if index_count > maximum_item_limit:
            remove_count = index_count - maximum_item_limit
            for _ in range(remove_count):
                self.takeItem(0)

    def show_fulltext(self, *args, **kwargs):
        selected_index = self.currentRow()

        selected_item = self.item(selected_index)
        fulltext = selected_item.fulltext

        def job():
            formation = ["This is the full log", FullLogView, True, [fulltext]]
            core.window.overlap(formation)

        thread_toss.apply_async(job)
