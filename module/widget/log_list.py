from PyQt6 import QtWidgets, QtGui


class LogList(QtWidgets.QListWidget):
    def __init__(self, parent):

        super().__init__(parent)
        fixed_width_font = QtGui.QFont("Consolas", 9)
        self.setFont(fixed_width_font)

    def addItem(self, text):  # noqa:N802

        maximum_item_limit = 256

        new_item = QtWidgets.QListWidgetItem(self)
        new_item.fulltext = text
        new_item.setText(text.split("\n")[0])

        super().addItem(new_item)

        index_count = self.count()

        if index_count > maximum_item_limit:
            remove_count = index_count - maximum_item_limit
            for _ in range(remove_count):
                self.takeItem(0)

    def selectionChanged(self, selected, deselected):  # noqa:N802

        selected_index = self.currentRow()
        index_count = self.count()

        selected_item = self.item(selected_index)
        fulltext = selected_item.fulltext
        selected_item.setText(fulltext)

        for index in range(index_count):
            if selected_index == index:
                continue
            target_item = self.item(index)
            current_text = target_item.text()
            if "\n" in current_text:
                one_line_text = target_item.fulltext.split("\n")[0]
                target_item.setText(one_line_text)

        super().selectionChanged(selected, deselected)

    def clearSelection(self):  # noqa:N802

        super().clearSelection()

        index_count = self.count()

        for index in range(index_count):
            target_item = self.item(index)
            current_text = target_item.text()
            if "\n" in current_text:
                one_line_text = target_item.fulltext.split("\n")[0]
                target_item.setText(one_line_text)
