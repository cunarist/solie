"""Worker team coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .collector import Collector
    from .manager import Manager
    from .simulator import Simulator
    from .strategist import Strategiest
    from .transactor import Transactor


type TeamMember = Collector | Transactor | Simulator | Strategiest | Manager


class Team:
    """Collection of all workers."""

    collector: Collector
    transactor: Transactor
    simulator: Simulator
    strategist: Strategiest
    manager: Manager

    def get_all(self) -> list[TeamMember]:
        """Get list of all workers."""
        workers: list[TeamMember] = [
            self.collector,
            self.transactor,
            self.simulator,
            self.strategist,
            self.manager,
        ]
        return workers
