from PyQt6 import QtGui
from pygments import lex, lexers


class SyntaxHighlighter(QtGui.QSyntaxHighlighter):
    def highlightBlock(self, script):  # noqa:N802

        current_position = 0

        for token, text_block in lex(script, self._lexer):
            length = len(text_block)
            text_format = None
            for text_type in self._mapping.keys():
                if str(token).startswith(text_type):
                    text_format = self._mapping[text_type]
                    break
            if text_format is not None:
                self.setFormat(current_position, length, text_format)
            current_position += length

    def __init__(self, parent=None):
        super().__init__(parent)

        self._lexer = lexers.PythonLexer()
        self._mapping = {}

        text_type = "Token.Error"
        hex_color = "#DD0000"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Keyword"
        hex_color = "#0077AA"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Name.Class"
        hex_color = "#DD4A68"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Name.Function"
        hex_color = "#DD4A68"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Literal.String"
        hex_color = "#669900"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Literal.Number"
        hex_color = "#990055"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Operator"
        hex_color = "#9A6E3A"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Punctuation"
        hex_color = "#999999"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format

        text_type = "Token.Comment"
        hex_color = "#708090"
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QBrush(QtGui.QColor(hex_color)))
        self._mapping[text_type] = text_format
