import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6 import QtGui, QtWidgets

from solie.common import PACKAGE_NAME, PACKAGE_PATH, spawn
from solie.widget import AskPopup, OverlayPopup
from solie.window import Window
from solie.worker import (
    Collector,
    Manager,
    Simulator,
    Strategiest,
    Transactor,
    team,
)

logger = logging.getLogger(__name__)


async def live(app: QtWidgets.QApplication):
    staticpath = PACKAGE_PATH / "static"
    QtGui.QFontDatabase.addApplicationFont(str(staticpath / "source_code_pro.ttf"))
    QtGui.QFontDatabase.addApplicationFont(str(staticpath / "notosans_regular.ttf"))
    QtGui.QFontDatabase.addApplicationFont(str(staticpath / "lexend_bold.ttf"))
    default_font = QtGui.QFont("Noto Sans", 9)
    app.setFont(default_font)

    dark_palette = QtGui.QPalette()
    color_role = QtGui.QPalette.ColorRole
    dark_palette.setColor(color_role.Window, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(color_role.WindowText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.Base, QtGui.QColor(22, 22, 22))
    dark_palette.setColor(color_role.AlternateBase, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(color_role.ToolTipBase, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.ToolTipText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.Text, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.Button, QtGui.QColor(29, 29, 29))
    dark_palette.setColor(color_role.ButtonText, QtGui.QColor(230, 230, 230))
    dark_palette.setColor(color_role.BrightText, QtGui.QColor(255, 180, 0))
    dark_palette.setColor(color_role.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(color_role.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(color_role.HighlightedText, QtGui.QColor(0, 0, 0))
    app.setStyle("Fusion")
    app.setPalette(dark_palette)

    close_event = asyncio.Event()
    scheduler = AsyncIOScheduler(timezone="UTC")

    window = Window(close_event)
    window.setPalette(dark_palette)
    AskPopup.install_window(window)
    OverlayPopup.install_window(window)

    logging.getLogger(PACKAGE_NAME).setLevel("DEBUG")
    await window.boot()
    logger.info("Started up")

    collector = Collector(window, scheduler)
    transactor = Transactor(window, scheduler)
    simulator = Simulator(window, scheduler)
    strategist = Strategiest(window, scheduler)
    manager = Manager(window, scheduler)

    team.unite(collector, transactor, simulator, strategist, manager)

    tasks = [
        spawn(collector.load()),
        spawn(transactor.load()),
        spawn(simulator.load()),
        spawn(strategist.load()),
        spawn(manager.load()),
    ]
    await asyncio.wait(tasks)

    spawn(collector.get_exchange_information())
    spawn(strategist.display_strategies())
    spawn(transactor.display_strategy_index())
    spawn(transactor.watch_binance())
    spawn(transactor.update_user_data_stream())
    spawn(transactor.display_lines())
    spawn(transactor.display_day_range())
    spawn(simulator.display_lines())
    spawn(simulator.display_year_range())
    spawn(simulator.display_available_years())
    spawn(manager.check_binance_limits())
    spawn(manager.display_internal_status())

    scheduler.start()
    await asyncio.sleep(1)

    window.reveal()
    await close_event.wait()

    scheduler.shutdown()
    await asyncio.sleep(1)

    tasks = [
        spawn(transactor.save_large_data()),
        spawn(transactor.save_scribbles()),
        spawn(strategist.save_strategies()),
        spawn(collector.save_candle_data()),
    ]
    await asyncio.wait(tasks)
