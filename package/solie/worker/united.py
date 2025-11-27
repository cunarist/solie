"""Worker protocol and team coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from solie.window import Window

if TYPE_CHECKING:
    from .collector import Collector
    from .manager import Manager
    from .simulator import Simulator
    from .strategist import Strategiest
    from .transactor import Transactor


class Worker(Protocol):
    """Worker protocol for task and data management.

    A worker owns its tasks and data.
    Each worker has a single responsibility.
    """

    def __init__(self, window: Window, scheduler: AsyncIOScheduler) -> None:
        """Initialize worker."""
        ...

    async def load_work(self) -> None:
        """Read work data from disk."""

    async def dump_work(self) -> None:
        """Write work data to disk."""


class Team:
    """Collection of all workers."""

    collector: Collector
    transactor: Transactor
    simulator: Simulator
    strategist: Strategiest
    manager: Manager

    def get_all(self) -> list[Worker]:
        """Get list of all workers."""
        return [
            self.collector,
            self.transactor,
            self.simulator,
            self.strategist,
            self.manager,
        ]


team = Team()
