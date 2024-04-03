import asyncio
import sys

from PySide6 import QtGui, QtWidgets

from solie.common import PACKAGE_PATH, prepare_process_pool
from solie.widget import AskPopup, OverlayPanel
from solie.window import Window
from solie.worker import Collector, Manager, Simulator, Strategiest, Transactor

app_close_event = asyncio.Event()


def bring_to_life():
    # Make the app.
    app = QtWidgets.QApplication(sys.argv)

    # Theme should be done after creating the app and before creating the window.
    staticpath = PACKAGE_PATH / "static"
    QtGui.QFontDatabase.addApplicationFont(str(staticpath / "source_code_pro.ttf"))
    QtGui.QFontDatabase.addApplicationFont(str(staticpath / "notosans_regular.ttf"))
    QtGui.QFontDatabase.addApplicationFont(str(staticpath / "lexend_bold.ttf"))
    default_font = QtGui.QFont("Noto Sans", 9)
    app.setFont(default_font)

    # Style the app.
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

    # Prepare the window.
    app_window = Window(app_close_event)
    app_window.setPalette(dark_palette)
    AskPopup.install_window(app_window)
    OverlayPanel.install_window(app_window)

    # Prepare the process pool
    prepare_process_pool()

    # Make the window do the job
    asyncio.run(live(app_window))

    # Make sure nothing happens after Solie.
    sys.exit()


async def live(window: Window):
    asyncio.create_task(window.boot())
    asyncio.create_task(window.process_ui_events())

    # Prepare workers
    collector = Collector(window)
    transactor = Transactor(window)
    simulator = Simulator(window)
    strategist = Strategiest(window)
    manager = Manager(window)

    await collector.load()
    await transactor.load()
    await simulator.load()
    await strategist.load()
    await manager.load()

    await app_close_event.wait()
