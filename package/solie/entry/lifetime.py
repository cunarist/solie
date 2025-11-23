from asyncio import Event, gather, sleep
from logging import getLogger

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from solie.common import PACKAGE_NAME, PACKAGE_PATH, spawn
from solie.utility import SolieConfig
from solie.widget import AskPopup, OverlayBox
from solie.window import Window
from solie.worker import (
    Collector,
    Manager,
    Simulator,
    Strategiest,
    Transactor,
    Worker,
    team,
)

logger = getLogger(__name__)


async def keep_processing_events(app: QApplication) -> None:
    """
    `Qt` does not have proper async support, as it is focused on threads.
    To use async-based concurrency, we need to periodically process UI events.
    Third-party polling libraries are not very reliable.
    """
    interval = 1 / 240
    while True:
        app.processEvents()
        await sleep(interval)


async def live(app: QApplication, config: SolieConfig) -> None:
    """Main application lifecycle management."""
    setup_fonts(app)
    setup_dark_theme(app)

    close_event = Event()
    scheduler = AsyncIOScheduler(timezone="UTC")

    window = create_and_setup_window(close_event, config)
    spawn(keep_processing_events(app))

    getLogger(PACKAGE_NAME).setLevel("DEBUG")
    await window.boot()
    logger.info("Started up")

    workers = create_workers(window, scheduler)
    await gather(*(worker.load_work() for worker in workers))
    spawn_worker_tasks()

    scheduler.start()
    await sleep(1)

    window.reveal()
    await close_event.wait()

    scheduler.shutdown()
    await sleep(1)

    await gather(*(worker.dump_work() for worker in workers))


def setup_fonts(app: QApplication) -> None:
    """Load and configure application fonts."""
    staticpath = PACKAGE_PATH / "static"
    QFontDatabase.addApplicationFont(str(staticpath / "source_code_pro.ttf"))
    QFontDatabase.addApplicationFont(str(staticpath / "notosans_regular.ttf"))
    QFontDatabase.addApplicationFont(str(staticpath / "lexend_bold.ttf"))
    default_font = QFont("Noto Sans", 9)
    app.setFont(default_font)


def setup_dark_theme(app: QApplication) -> None:
    """Configure dark theme palette for the application."""
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


def create_and_setup_window(close_event: Event, config: SolieConfig) -> Window:
    """Create and configure the main window."""
    window = Window(close_event, config)
    dark_palette = window.palette()  # Reuse the app's palette
    window.setPalette(dark_palette)
    AskPopup.install_window(window)
    OverlayBox.install_window(window)
    return window


def create_workers(window: Window, scheduler: AsyncIOScheduler) -> list[Worker]:
    """Create all worker instances and unite them as a team."""
    collector = Collector(window, scheduler)
    team.collector = collector
    transactor = Transactor(window, scheduler)
    team.transactor = transactor
    simulator = Simulator(window, scheduler)
    team.simulator = simulator
    strategist = Strategiest(window, scheduler)
    team.strategist = strategist
    manager = Manager(window, scheduler)
    team.manager = manager
    return team.get_all()


def spawn_worker_tasks() -> None:
    """Spawn initial tasks for all workers."""
    collector = team.collector
    transactor = team.transactor
    simulator = team.simulator
    strategist = team.strategist
    manager = team.manager

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
