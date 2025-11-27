"""Qt signal to async function connector."""

from collections.abc import Callable, Coroutine
from typing import Any

from PySide6.QtCore import SignalInstance

from .concurrency import spawn


def outsource(
    signal: SignalInstance,
    target_function: Callable[[], Coroutine[None, None, Any]],
) -> None:
    """Connect Qt signal to async function."""

    def job(*_args: Any, **_kwargs: Any) -> None:
        spawn(target_function())

    signal.connect(job)
