from pygments import lex, lexers
from PySide6 import QtGui


class SyntaxHighlighter(QtGui.QSyntaxHighlighter):
    def highlightBlock(self, text):
        current_position = 0

        for token, text_block in lex(text, self._lexer):
            length = len(text_block)
            text_format = None
            for text_type in self._mapping.keys():
                if str(token).startswith(text_type):
                    text_format = self._mapping[text_type]
                    break
            if text_format is not None:
                self.setFormat(current_position, length, text_format)
            current_position += length

    def __init__(self, parent):
        super().__init__(parent)

        self._lexer = lexers.PythonLexer()
        self._mapping = {}

        text_type = "Token.Keyword"
        hex_color = "#d1939e"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Literal.String"
        hex_color = "#bce051"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Literal.Number"
        hex_color = "#d1939e"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Operator"
        hex_color = "#f4b73d"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Punctuation"
        hex_color = "#999999"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Comment"
        hex_color = "#997f66"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format
