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
    def __init__(self, window: Window, scheduler: AsyncIOScheduler): ...
    async def load_work(self): ...
    async def dump_work(self): ...


class Team:
    def unite(
        self,
        collector: Collector,
        transactor: Transactor,
        simulator: Simulator,
        strategist: Strategiest,
        manager: Manager,
    ):
        self.collector = collector
        self.transactor = transactor
        self.simulator = simulator
        self.strategist = strategist
        self.manager = manager

    def get_all(self) -> list[Worker]:
        return [
            self.collector,
            self.transactor,
            self.simulator,
            self.strategist,
            self.manager,
        ]


team = Team()
