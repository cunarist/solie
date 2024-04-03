from .collector import Collector
from .manager import Manager
from .simulator import Simulator
from .strategist import Strategiest
from .transactor import Transactor


def remember_team(
    collector_member: Collector,
    transactor_member: Transactor,
    simulator_member: Simulator,
    strategist_member: Strategiest,
    manager_member: Manager,
):
    global collector
    global transactor
    global simulator
    global strategist
    global manager

    collector = collector_member
    transactor = transactor_member
    simulator = simulator_member
    strategist = strategist_member
    manager = manager_member
