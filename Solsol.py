import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from module import core  # type:ignore # noqa:F401
