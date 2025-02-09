from dataclasses import dataclass
from datetime import datetime
from enum import Enum

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


class BoardLockOptions(Enum):
    NEVER = 0
    SECONDS_10 = 1
    MINUTE_1 = 2
    MINUTE_10 = 3
    HOUR_1 = 4


@dataclass
class ManagementSettings(DataClassJsonMixin):
    lock_board: BoardLockOptions = BoardLockOptions.NEVER


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


@dataclass
class AggregateTrade:
    timestamp: int  # In milliseconds
    symbol: str
    price: float
    volume: float


class OrderType(Enum):
    NOW_BUY = 0
    NOW_SELL = 1
    NOW_CLOSE = 2
    CANCEL_ALL = 3
    BOOK_BUY = 4
    BOOK_SELL = 5
    LATER_UP_BUY = 6
    LATER_UP_SELL = 7
    LATER_UP_CLOSE = 8
    LATER_DOWN_BUY = 9
    LATER_DOWN_SELL = 10
    LATER_DOWN_CLOSE = 11
    OTHER = 12

    def is_now(self) -> bool:
        return self in (
            OrderType.NOW_BUY,
            OrderType.NOW_SELL,
            OrderType.NOW_CLOSE,
        )

    def is_book(self) -> bool:
        return self in (
            OrderType.BOOK_BUY,
            OrderType.BOOK_SELL,
        )

    def is_later(self) -> bool:
        return self in (
            OrderType.LATER_UP_BUY,
            OrderType.LATER_UP_SELL,
            OrderType.LATER_UP_CLOSE,
            OrderType.LATER_DOWN_BUY,
            OrderType.LATER_DOWN_SELL,
            OrderType.LATER_DOWN_CLOSE,
        )


class PositionDirection(Enum):
    SHORT = -1
    NONE = 0
    LONG = 1


@dataclass
class Decision(DataClassJsonMixin):
    boundary: float = 0.0
    margin: float = 0.0


@dataclass
class OpenOrder(DataClassJsonMixin):
    order_type: OrderType
    boundary: float
    """The price where this order gains effect"""
    left_margin: float | None
    """Amount of the asset to be invested, in dollars"""


@dataclass
class Position(DataClassJsonMixin):
    margin: float
    direction: PositionDirection
    entry_price: float
    update_time: datetime
    """Time of the last trade in this position"""


@dataclass
class AccountState(DataClassJsonMixin):
    observed_until: datetime
    wallet_balance: float
    """Total assets, in dollars"""
    positions: dict[str, Position]
    """Current position direction of a specific symbol"""
    open_orders: dict[str, dict[int, OpenOrder]]
