import sys
from asyncio import set_event_loop
from typing import NoReturn

from PySide6 import QtWidgets
from qasync import QEventLoop

from solie.common import prepare_process_pool

from .lifetime import live


def bring_to_life() -> NoReturn:
    prepare_process_pool()

    app = QtWidgets.QApplication()
    event_loop = QEventLoop(app)
    set_event_loop(event_loop)

    with event_loop:
        event_loop.run_until_complete(live(app))

    sys.exit()
