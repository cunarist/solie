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


BOARD_LOCK_OPTIONS = (
    "NEVER",
    "10_SECOND",
    "1_MINUTE",
    "10_MINUTE",
    "1_HOUR",
)


@dataclass
class ManagementSettings(DataClassJsonMixin):
    lock_board: str = "NEVER"  # One of `BOARD_LOCK_OPTIONS`


@dataclass
class BookTicker:
    timestamp: int  # In milliseconds
    symbol: str
    best_bid_price: float
    best_ask_price: float


@dataclass
class MarkPrice:
    timestamp: int  # In milliseconds
    symbol: str
    mark_price: float


RealtimeEvent = BookTicker | MarkPrice


@dataclass
class AggregateTrade:
    timestamp: int  # In milliseconds
    symbol: str
    price: float
    volume: float
