import multiprocessing
import sys

from tendo import singleton

from module import core

if __name__ == "__main__":
    multiprocessing.freeze_support()

    try:
        single_instance = singleton.SingleInstance()
        # prevent multiple instances of app running together
    except singleton.SingleInstanceException:
        sys.exit()

    core.bring_to_life()
