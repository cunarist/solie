from PySide6 import QtCore, QtGui, QtWidgets
from typing_extensions import override
from yapf.yapflib.errors import YapfError
from yapf.yapflib.yapf_api import FormatCode

from solie.utility import SyntaxHighlighter


class ScriptEditor(QtWidgets.QPlainTextEdit):
    def __init__(self, parent):
        super().__init__(parent)
        self.fixed_width_font = QtGui.QFont("Source Code Pro", 9)
        self.setFont(self.fixed_width_font)
        self.setLineWrapMode(ScriptEditor.LineWrapMode.NoWrap)
        SyntaxHighlighter(parent).setDocument(self.document())

    @override
    def keyPressEvent(self, e):
        event = e
        should_indent = event.key() == QtCore.Qt.Key.Key_Tab
        should_dedent = event.key() == QtCore.Qt.Key.Key_Backtab
        if should_indent or should_dedent:
            scroll_position = self.verticalScrollBar().value()
            text = self.toPlainText()
            text_cursor = self.textCursor()
            start_character = text_cursor.selectionStart()
            end_character = text_cursor.selectionEnd()
            start_line = text[:start_character].count("\n")
            end_line = text[:end_character].count("\n")
            each_lines = text.split("\n")
            for line_number in range(start_line, end_line + 1):
                if should_indent:
                    this_line = each_lines[line_number]
                    each_lines[line_number] = "    " + this_line
                elif should_dedent:
                    for _ in range(4):
                        this_line = each_lines[line_number]
                        if len(this_line) > 0 and this_line[0] == " ":
                            each_lines[line_number] = this_line[1:]
            text = "\n".join(each_lines)
            self.setPlainText(text)
            newline_positions = [turn for turn, char in enumerate(text) if char == "\n"]
            line_start_positions = [item + 1 for item in newline_positions]
            line_start_positions.insert(0, 0)
            line_end_positions = [item - 0 for item in newline_positions]
            line_end_positions.append(len(text))
            if start_line == end_line:
                text_cursor.setPosition(line_end_positions[end_line])
            else:
                select_from = line_start_positions[start_line]
                text_cursor.setPosition(select_from)
                select_to = line_end_positions[end_line]
                text_cursor.setPosition(
                    select_to, QtGui.QTextCursor.MoveMode.KeepAnchor
                )
            self.setTextCursor(text_cursor)
            self.verticalScrollBar().setValue(scroll_position)
            return
        return super().keyPressEvent(event)

    @override
    def focusOutEvent(self, e):
        event = e
        # apply formatter style
        scroll_position = self.verticalScrollBar().value()
        text = self.toPlainText()
        try:
            formatted_text, _ = FormatCode(text)
            self.setPlainText(formatted_text)
        except YapfError:
            pass
        self.verticalScrollBar().setValue(scroll_position)
        # run original function as well
        return super().focusOutEvent(event)
