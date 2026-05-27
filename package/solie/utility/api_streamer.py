"""WebSocket streaming for real-time market data."""

import json
from asyncio import (
    CancelledError,
    Task,
    current_task,
    sleep,
    wait,
    wait_for,
)
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from logging import getLogger
from types import TracebackType
from typing import Any, Self

from aiohttp import ClientError, ClientSession, WSMsgType

from solie.common import spawn

logger = getLogger(__name__)


class ApiStreamError(Exception):
    """Exception raised when API stream encounters an error."""

    def __init__(self, received: Any) -> None:
        """Initialize API stream error."""
        formatted = json.dumps(received, indent=2)
        super().__init__(formatted)


class ApiStreamer:
    """WebSocket API streamer."""

    def __init__(
        self,
        url: str,
        handler: Callable[[Any], Coroutine[None, None, Any]],
    ) -> None:
        """Initialize API streamer."""
        self._url = url
        self._handler = handler
        self._session: ClientSession | None = None
        self._is_open = False
        self._connected_since: datetime | None = None
        self._connection_task: Task[Any] | None = None
        self._handler_tasks: set[Task[Any]] = set()

    async def __aenter__(self) -> Self:
        """Enter the streamer connection scope."""
        if self._session is None or self._session.closed:
            self._session = ClientSession()
        if self._connection_task is None or self._connection_task.done():
            self._is_open = True
            self._connection_task = spawn(self._keep_connecting())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close WebSocket connection resources."""
        del exc_type, exc, traceback
        await self._close()

    @property
    def url(self) -> str:
        """Get WebSocket URL."""
        return self._url

    @property
    def connected_since(self) -> datetime | None:
        """Get the moment when the current WebSocket connection opened."""
        return self._connected_since

    async def _keep_connecting(self) -> None:
        while self._is_open:
            try:
                await self._keep_listening()
            except (ClientError, OSError, TimeoutError):
                # This happens when internet is disconnected, etc...
                logger.debug("Client error during websocket connection")
            await sleep(5.0)

    async def _keep_listening(self) -> None:
        session = self._require_session()
        self._connected_since = None
        async with session.ws_connect(self._url, heartbeat=5.0) as websocket:
            self._connected_since = datetime.now(UTC)
            logger.info("Websocket connected\n%s", self._url)
            try:
                async for message in websocket:
                    if message.type == WSMsgType.ERROR:
                        url = self._url
                        parsed = json.dumps(message.json(), indent=2)
                        logger.warning(
                            "Websocket got an error message\n%s\n%s",
                            url,
                            parsed,
                        )
                    else:
                        content = message.json()

                        def done_callback(
                            task: Task[Any],
                            content: Any = content,
                        ) -> None:
                            try:
                                error = task.exception()
                            except CancelledError:
                                return
                            if error:
                                raise ApiStreamError(content) from error

                        task = spawn(self._handler(content))
                        self._handler_tasks.add(task)
                        task.add_done_callback(self._handler_tasks.discard)
                        task.add_done_callback(done_callback)
            finally:
                self._connected_since = None
                logger.info("Websocket disconnected\n%s", self._url)

    async def _close(self) -> None:
        """Close WebSocket connection."""
        self._is_open = False
        self._connected_since = None
        session = self._session
        if session is not None and not session.closed:
            await session.close()
        task = self._connection_task
        if task is not None and task is not current_task() and not task.done():
            task.cancel()
            try:
                await wait_for(task, timeout=2.0)
            except (CancelledError, TimeoutError):
                pass
        self._connection_task = None
        await self._cancel_handler_tasks()

    async def _cancel_handler_tasks(self) -> None:
        running_task = current_task()
        tasks = [
            task
            for task in self._handler_tasks
            if task is not running_task and not task.done()
        ]
        if len(tasks) == 0:
            self._handler_tasks.clear()
            return
        for task in tasks:
            task.cancel()
        await wait(tasks, timeout=2.0)
        self._handler_tasks.clear()

    def _require_session(self) -> ClientSession:
        session = self._session
        if session is None or session.closed:
            msg = "ApiStreamer is not entered"
            raise RuntimeError(msg)
        return session
