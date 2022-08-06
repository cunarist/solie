import multiprocessing

from module import core


if __name__ == "__main__":
    # make pyinstaller executable work with multiprocessing
    multiprocessing.freeze_support()

    # create app
    core.bring_to_life()
