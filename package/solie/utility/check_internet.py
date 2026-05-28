"""Internet connectivity monitoring."""

import asyncio
from asyncio import CancelledError, Task, sleep, wait, wait_for
from collections.abc import Callable, Coroutine
from logging import getLogger
from types import TracebackType
from typing import Any, Self

from solie.common import spawn

logger = getLogger(__name__)


ATTEMPT_IP = (
    "1.0.0.1",  # Cloudflare
    "1.1.1.1",  # Cloudflare
    "208.67.222.222",  # OpenDNS
    "208.67.220.220",  # OpenDNS
)


class InternetMonitor:
    """Connection status owner with connect/disconnect callbacks."""

    def __init__(self) -> None:
        """Initialize connection monitor."""
        self.connected = False
        self._connected_calls: list[Callable[[], Coroutine[None, None, Any]]] = []
        self._disconnected_calls: list[Callable[[], Coroutine[None, None, Any]]] = []
        self._task: Task[Any] | None = None
        self._callback_tasks: set[Task[Any]] = set()

    async def __aenter__(self) -> Self:
        """Start monitoring internet connectivity."""
        await self._monitor_once()
        if self._task is None or self._task.done():
            self._task = spawn(self._keep_monitoring())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop monitoring internet connectivity."""
        del exc_type, exc, traceback
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await wait_for(task, timeout=2.0)
            except (CancelledError, TimeoutError):
                pass
        self._task = None
        if len(self._callback_tasks) == 0:
            return
        done, pending = await wait(self._callback_tasks, timeout=2.0)
        self._callback_tasks.difference_update(done)
        for callback_task in pending:
            callback_task.cancel()
        self._callback_tasks.clear()

    def when_connected(
        self,
        job: Callable[[], Coroutine[None, None, Any]],
    ) -> "InternetCallback":
        """Register callback for when internet connects."""
        return InternetCallback(self._connected_calls, job)

    def when_disconnected(
        self,
        job: Callable[[], Coroutine[None, None, Any]],
    ) -> "InternetCallback":
        """Register callback for when internet disconnects."""
        return InternetCallback(self._disconnected_calls, job)

    async def _keep_monitoring(self) -> None:
        while True:
            await self._monitor_once()
            await sleep(1)

    async def _monitor_once(self) -> None:
        was_connected = self.connected
        analyzed = False
        for attempt_ip in ATTEMPT_IP:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(attempt_ip, 53),
                    timeout=3,
                )
                writer.close()
                await writer.wait_closed()
                analyzed = True
                break
            except Exception:
                logger.debug("Failed to connect to %s", attempt_ip)
        self.connected = analyzed

        if was_connected and not self.connected:
            for job in self._disconnected_calls:
                self._spawn_callback(job())
            logger.warning("Internet disconnected")
        elif not was_connected and self.connected:
            for job in self._connected_calls:
                self._spawn_callback(job())
            logger.info("Internet connected")

    def _spawn_callback(self, coroutine: Coroutine[None, None, Any]) -> None:
        task = spawn(coroutine)
        self._callback_tasks.add(task)
        task.add_done_callback(self._callback_tasks.discard)


class InternetCallback:
    """Context-owned internet-status callback registration."""

    def __init__(
        self,
        callbacks: list[Callable[[], Coroutine[None, None, Any]]],
        job: Callable[[], Coroutine[None, None, Any]],
    ) -> None:
        """Initialize callback registration."""
        self._callbacks = callbacks
        self._job = job

    def __enter__(self) -> Self:
        """Register callback."""
        self._callbacks.append(self._job)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Unregister callback."""
        del exc_type, exc, traceback
        try:
            self._callbacks.remove(self._job)
        except ValueError:
            pass
