import asyncio

from PySide6 import QtWidgets


class BaseOverlay(QtWidgets.QWidget):
    done_event = asyncio.Event()
