import multiprocessing
import sys

from tendo import singleton

from module import core

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # ■■■■■ prevent multiple instances of app running together ■■■■■

    try:
        single_instance = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit()

    # ■■■■■ create app ■■■■■
    core.bring_to_life()
