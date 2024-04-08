import asyncio
import json
import logging
from typing import Callable, Coroutine

from aiohttp import ClientSession, WSMsgType

logger = logging.getLogger(__name__)


class ApiStreamError(Exception):
    def __init__(self, received: dict | list):
        formatted = json.dumps(received, indent=2)
        super().__init__(formatted)


class ApiStreamer:
    def __init__(
        self,
        url: str,
        handler: Callable[[dict], Coroutine] | Callable[[list], Coroutine],
    ):
        self._url = url
        self._handler = handler
        self._session = ClientSession()

        self._task = asyncio.create_task(self._keep_listening())

    async def _keep_listening(self):
        async with self._session.ws_connect(self._url) as websocket:
            logger.info(f"Websocket connected: {self._url}")
            async for received_raw in websocket:
                stop_types = (WSMsgType.CLOSED, WSMsgType.ERROR)
                if received_raw.type in stop_types:
                    logger.info(f"Websocket closed: {self._url}")
                    break
                else:
                    received = received_raw.json()

                    def done_callback(task: asyncio.Task, received=received):
                        error = task.exception()
                        if error:
                            raise ApiStreamError(received) from error

                    task = asyncio.create_task(self._handler(received))
                    task.add_done_callback(done_callback)
            logger.info(f"Websocket stopped: {self._url}")

    async def close(self):
        await self._session.close()
