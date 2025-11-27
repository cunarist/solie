"""Application entry point."""

import sys
from asyncio import run
from typing import NoReturn

from PySide6.QtWidgets import QApplication

from solie.common import prepare_process_pool
from solie.utility import SolieConfig

from .lifetime import live


def bring_to_life(config: SolieConfig | None = None) -> NoReturn:
    """Start Solie application and show main window."""
    prepare_process_pool()

    if config is None:
        config = SolieConfig()

    app = QApplication()
    run(live(app, config))

    sys.exit()
