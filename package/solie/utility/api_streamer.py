"""WebSocket streaming for real-time market data."""

import json
from asyncio import Task, sleep
from collections.abc import Callable, Coroutine
from logging import getLogger
from typing import Any

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
        self._session = ClientSession()
        self._is_open = True

        spawn(self._keep_connecting())

    @property
    def url(self) -> str:
        """Get WebSocket URL."""
        return self._url

    async def _keep_connecting(self) -> None:
        while self._is_open:
            try:
                await self._keep_listening()
            except ClientError:
                # This happens when internet is disconnected, etc...
                logger.debug("Client error during websocket connection")
            await sleep(5.0)

    async def _keep_listening(self) -> None:
        async with self._session.ws_connect(self._url, heartbeat=5.0) as websocket:
            logger.info("Websocket connected\n%s", self._url)
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

                    def done_callback(task: Task[Any], content: Any = content) -> None:
                        error = task.exception()
                        if error:
                            raise ApiStreamError(content) from error

                    task = spawn(self._handler(content))
                    task.add_done_callback(done_callback)
            logger.info("Websocket disconnected\n%s", self._url)

    async def close(self) -> None:
        """Close WebSocket connection."""
        self._is_open = False
        await self._session.close()
