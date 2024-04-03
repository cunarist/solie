import asyncio
import sys

from PySide6 import QtGui, QtWidgets

from solie.common import PACKAGE_PATH, prepare_process_pool
from solie.window import Window


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

    # Show the window.
    app_window = Window()
    app_window.setPalette(dark_palette)

    # Prepare tasks.
    prepare_process_pool()
    asyncio.run(app_window.live())

    # Make sure nothing happens after Solie.
    sys.exit()
