import asyncio
import logging
from typing import Callable, Coroutine

import aiohttp

logger = logging.getLogger(__name__)

is_internet_checked = asyncio.Event()
was_connected = False
connected_functions: list[Callable[..., Coroutine]] = []
disconnected_functions: list[Callable[..., Coroutine]] = []


def internet_connected():
    if is_internet_checked.is_set():
        return was_connected
    else:
        raise RuntimeError("Internet connection is not being monitored")


async def monitor_internet():
    global was_connected
    while True:
        # try to connect to DNS servers
        attempt_ips = [
            "1.0.0.1",  # Cloudflare
            "1.1.1.1",  # Cloudflare
            "8.8.4.4",  # Google
            "8.8.8.8",  # Google
            "9.9.9.9",  # Quad9
            "149.112.112.112",  # Quad9
            "208.67.222.222",  # OpenDNS
            "208.67.220.220",  # OpenDNS
        ]
        is_connected = False
        async with aiohttp.ClientSession() as session:
            for attempt_ip in attempt_ips:
                try:
                    async with session.get(f"http://{attempt_ip}") as response:
                        if response.status == 200:
                            is_connected = True
                            break
                except Exception:
                    pass

        # detect changes
        if was_connected and not is_connected:
            for job in disconnected_functions:
                asyncio.create_task(job())
            logger.warning("Internet disconnected")
        elif not was_connected and is_connected:
            for job in connected_functions:
                asyncio.create_task(job())
            logger.info("Internet connected")

        # remember connection state
        was_connected = is_connected
        is_internet_checked.set()

        # wait for a while
        await asyncio.sleep(1)


def add_connected_functions(job: Callable[..., Coroutine]):
    global connected_functions
    connected_functions.append(job)


def add_disconnected_functions(job: Callable[..., Coroutine]):
    global disconnected_functions
    disconnected_functions.append(job)
