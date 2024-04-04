import asyncio
from typing import Callable, Coroutine

from PySide6.QtCore import SignalInstance


def outsource(signal: SignalInstance, target_function: Callable[[], Coroutine]):
    def job(*args, **kwargs):
        asyncio.create_task(target_function())

    signal.connect(job)
