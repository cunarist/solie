from asyncio import Event, sleep, wait
from logging import getLogger

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from solie.common import PACKAGE_NAME, PACKAGE_PATH, spawn
from solie.utility import SolieConfig
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

logger = getLogger(__name__)


async def keep_processing_events(app: QApplication):
    """
    `Qt` does not have proper async support, as it is focused on threads.
    To use async-based concurrency, we need to periodically process UI events.
    Third-party polling libraries are not very reliable.
    """
    interval = 1 / 240
    while True:
        app.processEvents()
        await sleep(interval)


async def live(app: QApplication, config: SolieConfig):
    staticpath = PACKAGE_PATH / "static"
    QFontDatabase.addApplicationFont(str(staticpath / "source_code_pro.ttf"))
    QFontDatabase.addApplicationFont(str(staticpath / "notosans_regular.ttf"))
    QFontDatabase.addApplicationFont(str(staticpath / "lexend_bold.ttf"))
    default_font = QFont("Noto Sans", 9)
    app.setFont(default_font)

    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(29, 29, 29))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(230, 230, 230))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(22, 22, 22))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(29, 29, 29))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(230, 230, 230))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(230, 230, 230))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(230, 230, 230))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(29, 29, 29))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(230, 230, 230))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 180, 0))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setStyle("Fusion")
    app.setPalette(dark_palette)

    close_event = Event()
    scheduler = AsyncIOScheduler(timezone="UTC")

    window = Window(close_event, config)
    window.setPalette(dark_palette)
    AskPopup.install_window(window)
    OverlayPopup.install_window(window)
    spawn(keep_processing_events(app))

    getLogger(PACKAGE_NAME).setLevel("DEBUG")
    await window.boot()
    logger.info("Started up")

    collector = Collector(window, scheduler)
    transactor = Transactor(window, scheduler)
    simulator = Simulator(window, scheduler)
    strategist = Strategiest(window, scheduler)
    manager = Manager(window, scheduler)
    team.unite(collector, transactor, simulator, strategist, manager)

    await wait(spawn(worker.load_work()) for worker in team.get_all())

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
    await sleep(1)

    window.reveal()
    await close_event.wait()

    scheduler.shutdown()
    await sleep(1)

    await wait(spawn(worker.dump_work()) for worker in team.get_all())
