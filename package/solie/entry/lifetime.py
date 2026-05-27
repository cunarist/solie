"""Application lifecycle management and initialization."""

from asyncio import Event, sleep
from contextlib import AsyncExitStack
from logging import INFO, getLogger

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from solie.common import (
    PACKAGE_NAME,
    PACKAGE_PATH,
    spawn,
)
from solie.utility import InternetMonitor, SolieConfig
from solie.window import Window
from solie.worker import (
    Collector,
    Manager,
    Simulator,
    Strategiest,
    Team,
    Transactor,
)

logger = getLogger(__name__)


async def keep_processing_events(app: QApplication) -> None:
    """Periodically process UI events.

    `Qt` does not have proper async support, as it is focused on threads.
    To use async-based concurrency, we need to periodically process UI events.
    Third-party polling libraries are not very reliable.
    """
    interval = 1 / 240
    while True:
        app.processEvents()
        await sleep(interval)


async def live(app: QApplication, config: SolieConfig) -> None:
    """Manage main application lifecycle."""
    setup_fonts(app)
    setup_dark_theme(app)

    await _live_with_contexts(app, config)


async def _live_with_contexts(
    app: QApplication,
    config: SolieConfig,
) -> None:
    """Manage application lifecycle inside resource scopes."""
    close_event = Event()
    scheduler = AsyncIOScheduler(timezone="UTC")
    internet_monitor = InternetMonitor()
    team = Team()
    window = create_and_setup_window(
        close_event,
        config,
        internet_monitor,
    )
    spawn(keep_processing_events(app))

    async with window:
        getLogger(PACKAGE_NAME).setLevel(INFO)
        logger.info("Started up")

        workers = create_workers(window, scheduler, team)
        async with AsyncExitStack() as worker_stack:
            for worker in workers:
                await worker_stack.enter_async_context(worker)

            spawn_worker_tasks(team)

            scheduler.start()
            worker_stack.callback(scheduler.shutdown, wait=False)
            await sleep(1)

            window.reveal()
            await close_event.wait()


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


def create_and_setup_window(
    close_event: Event,
    config: SolieConfig,
    internet_monitor: InternetMonitor,
) -> Window:
    """Create and configure the main window."""
    window = Window(close_event, config, internet_monitor)
    dark_palette = window.palette()  # Reuse the app's palette
    window.setPalette(dark_palette)
    return window


def create_workers(
    window: Window,
    scheduler: AsyncIOScheduler,
    team: Team,
) -> list[Collector | Transactor | Simulator | Strategiest | Manager]:
    """Create all worker instances and unite them as a team."""
    collector = Collector(window, scheduler, team)
    team.collector = collector
    transactor = Transactor(window, scheduler, team)
    team.transactor = transactor
    simulator = Simulator(window, scheduler, team)
    team.simulator = simulator
    strategist = Strategiest(window, scheduler)
    team.strategist = strategist
    manager = Manager(window, scheduler, team)
    team.manager = manager
    return team.get_all()


def spawn_worker_tasks(team: Team) -> None:
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
