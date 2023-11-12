import asyncio
import logging
from typing import Callable, Coroutine

import aiohttp


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
        async with self.session.ws_connect(self._url) as ws:
            async for received_raw in ws:
                if received_raw.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    asyncio.create_task(self._run_websocket())
                    raise ConnectionError(f"Websocket reconnected:\n{self._url}")
                else:
                    received = received_raw.json()
                    asyncio.create_task(self._when_received(received=received))

    async def _close_self(self):
        await self.session.close()
        logger = logging.getLogger("solie")
        logger.exception(f"Websocket closed:\n{self._url}")
