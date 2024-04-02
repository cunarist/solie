from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin


@dataclass
class Strategy(DataClassJsonMixin):
    code_name: str
    readable_name: str = "A New Blank Strategy"
    version: str = "1.0"
    description: str = "A blank strategy template before being written"
    risk_level: int = 2  # 2 means high, 1 means middle, 0 means low
    parallelized_simulation: bool = False
    chunk_division: int = 30
    indicators_script: str = "pass"
    decision_script: str = "pass"


@dataclass
class Strategies(DataClassJsonMixin):
    all: list[Strategy]


@dataclass
class TransactionSettings(DataClassJsonMixin):
    strategy_index: int = 0
    should_transact: bool = False
    desired_leverage: int = 1
    binance_api_key: str = ""
    binance_api_secret: str = ""


@dataclass
class SimulationSettings:
    year: int
    strategy_index: int = 0
    maker_fee: float = 0.02
    taker_fee: float = 0.04
    leverage: int = 1


@dataclass
class SimulationSummary:
    year: int
    strategy_code_name: str
    strategy_version: str
