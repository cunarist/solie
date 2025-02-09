import json
import logging
from asyncio import Task, sleep
from typing import Any, Callable, Coroutine

from aiohttp import ClientError, ClientSession, WSMsgType

from solie.common import spawn

logger = logging.getLogger(__name__)


class ApiStreamError(Exception):
    def __init__(self, received: dict | list):
        formatted = json.dumps(received, indent=2)
        super().__init__(formatted)


class ApiStreamer:
    def __init__(
        self,
        url: str,
        handler: Callable[[dict], Coroutine[None, None, Any]]
        | Callable[[list], Coroutine[None, None, Any]],
    ):
        self._url = url
        self._handler = handler
        self._session = ClientSession()
        self._is_open = True

        spawn(self._keep_connecting())

    @property
    def url(self) -> str:
        return self._url

    async def _keep_connecting(self):
        while self._is_open:
            try:
                await self._keep_listening()
            except ClientError:
                # This happens when internet is disconnected, etc...
                pass
            await sleep(5.0)

    async def _keep_listening(self):
        async with self._session.ws_connect(self._url, heartbeat=5.0) as websocket:
            logger.info(f"Websocket connected\n{self._url}")
            async for message in websocket:
                if message.type == WSMsgType.ERROR:
                    url = self._url
                    parsed = json.dumps(message.json(), indent=2)
                    logger.warning(f"Websocket got an error message\n{url}\n{parsed}")
                else:
                    content = message.json()

                    def done_callback(task: Task[Any], content=content):
                        error = task.exception()
                        if error:
                            raise ApiStreamError(content) from error

                    task = spawn(self._handler(content))
                    task.add_done_callback(done_callback)
            logger.info(f"Websocket disconnected\n{self._url}")

    async def close(self):
        self._is_open = False
        await self._session.close()
