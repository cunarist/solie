from datetime import datetime
from enum import Enum
from typing import Any, NamedTuple, Protocol

import pandas as pd
from pydantic import BaseModel

# We use `BaseModel` when parsing, validation, or mutability is needed.
# Otherwise, `NamedTuple` is preferred because it's more performant.


class DataSettings(BaseModel):
    asset_token: str
    target_symbols: list[str]


class TransactionSettings(BaseModel):
    strategy_index: int = 0
    should_transact: bool = False
    desired_leverage: int = 1
    binance_api_key: str = ""
    binance_api_secret: str = ""


class SimulationSettings(BaseModel):
    year: int
    strategy_index: int = 0
    maker_fee: float = 0.02
    taker_fee: float = 0.04
    leverage: int = 1


class SimulationSummary(BaseModel):
    year: int
    strategy_code_name: str
    strategy_version: str


class BoardLockOptions(Enum):
    NEVER = 0
    SECONDS_10 = 1
    MINUTE_1 = 2
    MINUTE_10 = 3
    HOUR_1 = 4


class ManagementSettings(BaseModel):
    lock_board: BoardLockOptions = BoardLockOptions.NEVER


class BookTicker(NamedTuple):
    timestamp: int  # In milliseconds
    symbol: str
    best_bid_price: float
    best_ask_price: float


class MarkPrice(NamedTuple):
    timestamp: int  # In milliseconds
    symbol: str
    mark_price: float


class AggregateTrade(NamedTuple):
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


class Decision(BaseModel):
    boundary: float = 0.0
    margin: float = 0.0


class OpenOrder(BaseModel):
    order_type: OrderType
    boundary: float
    """The price where this order gains effect"""
    left_margin: float | None
    """Amount of the asset to be invested, in dollars"""


class Position(BaseModel):
    margin: float
    direction: PositionDirection
    entry_price: float
    update_time: datetime
    """Time of the last trade in this position"""


class AccountState(BaseModel):
    observed_until: datetime
    wallet_balance: float
    """Total assets, in dollars"""
    positions: dict[str, Position]
    """Current position direction of a specific symbol"""
    open_orders: dict[str, dict[int, OpenOrder]]


class VirtualPosition(BaseModel):
    """Virtual position inside simulation"""

    amount: float
    entry_price: float


class VirtualPlacement(BaseModel):
    """Virtual order that has been placed during simulation"""

    boundary: float
    """The price where this order gains effect"""
    margin: float
    """Amount of the asset to be invested, in dollars"""
    order_id: int


class VirtualState(BaseModel):
    """Virtual account state used in simulation"""

    available_balance: float
    positions: dict[str, VirtualPosition]
    placements: dict[str, dict[OrderType, VirtualPlacement]]


class RiskLevel(Enum):
    LOW = 0
    MIDDLE = 1
    HIGH = 2


class IndicatorInput(NamedTuple):
    target_symbols: list[str]
    candle_data: pd.DataFrame
    new_indicators: dict[str, pd.Series]


class DecisionInput(NamedTuple):
    target_symbols: list[str]
    account_state: AccountState
    current_moment: datetime
    current_candle_data: dict[str, float]
    current_indicators: dict[str, float]
    scribbles: dict[Any, Any]
    new_decisions: dict[str, dict[OrderType, Decision]]


class Strategy(Protocol):
    code_name: str
    readable_name: str
    version: str
    description: str
    risk_level: RiskLevel
    parallelized_simulation: bool
    chunk_division: int

    def create_indicators(self, given: IndicatorInput): ...
    def create_decisions(self, given: DecisionInput): ...
