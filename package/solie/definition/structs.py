from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin


@dataclass
class DownloadPreset:
    symbol: str
    unit_size: str  # "daily" or "monthly"
    year: int
    month: int
    day: int = 0  # Valid only when `unit_size` is "daily"


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
