from collections.abc import Callable, Coroutine
from typing import Any

from PySide6.QtCore import SignalInstance

from .concurrency import spawn


def outsource(
    signal: SignalInstance,
    target_function: Callable[[], Coroutine[None, None, Any]],
) -> None:
    def job(*args, **kwargs) -> None:
        spawn(target_function())

    signal.connect(job)
