from asyncio import Event, sleep
from collections.abc import Callable, Coroutine
from logging import getLogger
from typing import Any

from aiohttp import ClientSession

from solie.common import spawn

logger = getLogger(__name__)


ATTEMPT_IP = [
    "1.0.0.1",  # Cloudflare
    "1.1.1.1",  # Cloudflare
    "208.67.222.222",  # OpenDNS
    "208.67.220.220",  # OpenDNS
]

is_connected = False
is_internet_checked = Event()

connected_functions: list[Callable[[], Coroutine[None, None, Any]]] = []
disconnected_functions: list[Callable[[], Coroutine[None, None, Any]]] = []


def internet_connected():
    if is_internet_checked.is_set():
        return is_connected
    else:
        raise RuntimeError("Internet connection is not being monitored")


async def monitor_internet():
    global is_connected
    while True:
        # Try to connect to DNS servers and analyze internet connection
        was_connected = is_connected
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
        is_connected = analyzed
        is_internet_checked.set()

        # Detect changes
        if was_connected and not is_connected:
            for job in disconnected_functions:
                spawn(job())
            logger.warning("Internet disconnected")
        elif not was_connected and is_connected:
            for job in connected_functions:
                spawn(job())
            logger.info("Internet connected")

        # Wait for a while
        await sleep(1)


def when_internet_connected(job: Callable[[], Coroutine[None, None, Any]]):
    global connected_functions
    connected_functions.append(job)


def when_internet_disconnected(job: Callable[[], Coroutine[None, None, Any]]):
    global disconnected_functions
    disconnected_functions.append(job)
