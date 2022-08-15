import multiprocessing
import sys

from tendo import singleton

from module import core
from module.recipe import user_settings

user_settings.load()

if __name__ == "__main__":
    # even when frozen with pyinstaller
    multiprocessing.freeze_support()

    # from here only happens on the main process
    # prevent multiple instances of app running together
    try:
        single_instance = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit()

    # create app
    core.bring_to_life()
