from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .collector import Collector
    from .manager import Manager
    from .simulator import Simulator
    from .strategist import Strategiest
    from .transactor import Transactor


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


team = Team()
