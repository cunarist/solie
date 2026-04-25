"""Internet connectivity monitoring."""

import asyncio
from asyncio import sleep
from collections.abc import Callable, Coroutine
from logging import getLogger
from typing import Any, ClassVar

from solie.common import spawn

logger = getLogger(__name__)


ATTEMPT_IP = [
    "1.0.0.1",  # Cloudflare
    "1.1.1.1",  # Cloudflare
    "208.67.222.222",  # OpenDNS
    "208.67.220.220",  # OpenDNS
]


class StatusHolder:
    """Holds internet connection status and callbacks."""

    is_connected: ClassVar[bool] = False
    connected_calls: ClassVar[list[Callable[[], Coroutine[None, None, Any]]]] = []
    disconnected_calls: ClassVar[list[Callable[[], Coroutine[None, None, Any]]]] = []


def internet_connected() -> bool:
    """Check if internet is currently connected."""
    return StatusHolder.is_connected


async def start_monitoring_internet() -> None:
    """Start monitoring internet connectivity."""
    # Ensure that internet connection is initially checked
    # when this function returns.
    await monitor_internet()
    # Repeatedly monitor the internet status.
    spawn(keep_monitoring_internet())


async def keep_monitoring_internet() -> None:
    """Continuously monitor internet connectivity."""
    while True:
        await monitor_internet()
        await sleep(1)


async def monitor_internet() -> None:
    """Check internet status and trigger callbacks."""
    # Try to connect to DNS servers on port 53 (TCP) to check internet.
    was_connected = StatusHolder.is_connected
    analyzed = False
    for attempt_ip in ATTEMPT_IP:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(attempt_ip, 53),
                timeout=3,
            )
            writer.close()
            await writer.wait_closed()
            analyzed = True
            break
        except Exception:
            logger.debug("Failed to connect to %s", attempt_ip)
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
    """Register callback for when internet connects."""
    StatusHolder.connected_calls.append(job)


def when_internet_disconnected(job: Callable[[], Coroutine[None, None, Any]]) -> None:
    """Register callback for when internet disconnects."""
    StatusHolder.disconnected_calls.append(job)
