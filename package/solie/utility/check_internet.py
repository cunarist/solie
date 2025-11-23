from asyncio import sleep
from collections.abc import Callable, Coroutine
from logging import getLogger
from typing import Any, ClassVar

from aiohttp import ClientSession

from solie.common import spawn

logger = getLogger(__name__)


ATTEMPT_IP = [
    "1.0.0.1",  # Cloudflare
    "1.1.1.1",  # Cloudflare
    "208.67.222.222",  # OpenDNS
    "208.67.220.220",  # OpenDNS
]


class StatusHolder:
    is_connected: ClassVar[bool] = False
    connected_calls: ClassVar[list[Callable[[], Coroutine[None, None, Any]]]] = []
    disconnected_calls: ClassVar[list[Callable[[], Coroutine[None, None, Any]]]] = []


def internet_connected() -> bool:
    return StatusHolder.is_connected


async def start_monitoring_internet() -> None:
    # Ensure that internet connection is initially checked
    # when this function returns.
    await monitor_internet()
    # Repeatedly monitor the internet status.
    spawn(keep_monitoring_internet())


async def keep_monitoring_internet() -> None:
    while True:
        await monitor_internet()
        await sleep(1)


async def monitor_internet() -> None:
    # Try to connect to DNS servers and analyze internet connection.
    was_connected = StatusHolder.is_connected
    analyzed = False
    async with ClientSession() as session:
        for attempt_ip in ATTEMPT_IP:
            try:
                async with session.get(f"http://{attempt_ip}") as response:
                    if response.ok:
                        analyzed = True
                        break
            except Exception:
                pass
    StatusHolder.is_connected = analyzed

    # Detect changes.
    if was_connected and not StatusHolder.is_connected:
        for job in StatusHolder.disconnected_calls:
            spawn(job())
        logger.warning("Internet disconnected")
    elif not was_connected and StatusHolder.is_connected:
        for job in StatusHolder.connected_calls:
            spawn(job())
        logger.info("Internet connected")


def when_internet_connected(job: Callable[[], Coroutine[None, None, Any]]) -> None:
    StatusHolder.connected_calls.append(job)


def when_internet_disconnected(job: Callable[[], Coroutine[None, None, Any]]) -> None:
    StatusHolder.disconnected_calls.append(job)
