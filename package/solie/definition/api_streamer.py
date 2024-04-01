import asyncio
import logging
from typing import Callable, Coroutine

import aiohttp

logger = logging.getLogger(__name__)


class ApiStreamer:
    def __init__(self, url: str, when_received: Callable[..., Coroutine]):
        self._url = url
        self._when_received = when_received
        self.session = aiohttp.ClientSession()

        if url != "":
            asyncio.create_task(self._run_websocket())

    def __del__(self):
        asyncio.create_task(self._close_self())

    async def _run_websocket(self):
        while True:
            try:
                async with self.session.ws_connect(self._url) as websocket:
                    logger.info(f"Websocket connected: {self._url}")
                    async for received_raw in websocket:
                        if received_raw.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            logger.info(f"Websocket closed: {self._url}")
                            break
                        else:
                            received = received_raw.json()
                            asyncio.create_task(self._when_received(received=received))
                    logger.info(f"Websocket stopped: {self._url}")
            except Exception as error:
                # Handle errors that might occur due to network issues
                logger.exception(f"Websocket error: {error}")
                # Wait for a few seconds before attempting to reconnect
                await asyncio.sleep(5)

    async def _close_self(self):
        await self.session.close()
