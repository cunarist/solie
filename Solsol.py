import multiprocessing
import sys
import os

import pandas as pd
import pyqtgraph
from tendo import singleton

from module import core

if __name__ == "__main__":
    # ■■■■■ prevent multiple instances of app running together ■■■■■

    multiprocessing.freeze_support()

    # ■■■■■ prevent multiple instances of app running together ■■■■■

    try:
        single_instance = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit()

    # ■■■■■ global settings of packages ■■■■■

    os.get_terminal_size = lambda *args: os.terminal_size((72, 80))
    pd.set_option("display.precision", 3)
    pd.set_option("display.min_rows", 20)
    pd.set_option("display.max_rows", 20)
    pyqtgraph.setConfigOptions(antialias=True)

    # ■■■■■ create app ■■■■■
    core.bring_to_life()
