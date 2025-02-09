from typing import Callable, Coroutine

from PySide6.QtCore import SignalInstance

from .concurrency import spawn


def outsource(signal: SignalInstance, target_function: Callable[[], Coroutine]):
    def job(*args, **kwargs):
        spawn(target_function())

    signal.connect(job)
