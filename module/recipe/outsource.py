import asyncio
from typing import Callable, Coroutine

from PySide6.QtCore import SignalInstance


def do(signal: SignalInstance, target_function: Callable[..., Coroutine]):
    def job(*args):
        asyncio.create_task(target_function(*args))

    signal.connect(job)
