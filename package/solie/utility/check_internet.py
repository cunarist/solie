from asyncio import Event, sleep
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
    is_internet_checked: ClassVar[Event] = Event()
    connected_calls: ClassVar[list[Callable[[], Coroutine[None, None, Any]]]] = []
    disconnected_calls: ClassVar[list[Callable[[], Coroutine[None, None, Any]]]] = []


def internet_connected():
    if StatusHolder.is_internet_checked.is_set():
        return StatusHolder.is_connected
    else:
        raise RuntimeError("Internet connection is not being monitored")


async def start_monitoring_internet():
    spawn(keep_monitoring_internet())
    await StatusHolder.is_internet_checked.wait()


async def keep_monitoring_internet():
    while True:
        # Try to connect to DNS servers and analyze internet connection
        was_connected = StatusHolder.is_connected
        analyzed = False
        async with ClientSession() as session:
            for attempt_ip in ATTEMPT_IP:
                try:
                    async with session.get(f"http://{attempt_ip}") as response:
                        if response.status == 200:
                            analyzed = True
                            break
                except Exception:
                    pass
        StatusHolder.is_connected = analyzed
        StatusHolder.is_internet_checked.set()

        # Detect changes
        if was_connected and not StatusHolder.is_connected:
            for job in StatusHolder.disconnected_calls:
                spawn(job())
            logger.warning("Internet disconnected")
        elif not was_connected and StatusHolder.is_connected:
            for job in StatusHolder.connected_calls:
                spawn(job())
            logger.info("Internet connected")

        # Wait for a while
        await sleep(1)


def when_internet_connected(job: Callable[[], Coroutine[None, None, Any]]):
    StatusHolder.connected_calls.append(job)


def when_internet_disconnected(job: Callable[[], Coroutine[None, None, Any]]):
    StatusHolder.disconnected_calls.append(job)
