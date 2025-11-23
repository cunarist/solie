import math
import random
from datetime import datetime, timedelta, timezone
from enum import Enum
from itertools import product
from multiprocessing.managers import ListProxy
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from solie.utility import (
    COLUMN_PARTS_COUNT,
    AccountState,
    Decision,
    DecisionInput,
    IndicatorInput,
    OpenOrder,
    OrderType,
    Position,
    PositionDirection,
    SavedStrategy,
    Strategy,
    VirtualPlacement,
    VirtualState,
)

GRAPH_TYPES = ["PRICE", "VOLUME", "ABSTRACT"]


class DecisionContext(NamedTuple):
    """Context for making trading decisions."""

    strategy: Strategy
    target_symbols: list[str]
    current_moment: datetime
    current_candle_data: dict[str, float]
    current_indicators: dict[str, float]
    account_state: AccountState
    scribbles: dict[Any, Any]


class TradeAmounts(NamedTuple):
    """Trade amount details."""

    amount_shift: float
    fill_price: float


class TradeMoments(NamedTuple):
    """Trade timing details."""

    current_moment: datetime
    before_moment: datetime


class TradeDetails(NamedTuple):
    """Trade execution details."""

    before_moment: datetime
    amount_shift: float
    open_price: float


def make_indicators(
    strategy: Strategy,
    target_symbols: list[str],
    candle_data: pd.DataFrame,
    only_last_index: bool = False,
) -> pd.DataFrame:
    candle_data = candle_data.interpolate()

    if len(candle_data) > 0:
        dummy_index = candle_data.index[-1] + timedelta(seconds=1)
    else:
        dummy_index = datetime.fromtimestamp(0.0, tz=timezone.utc)

    candle_data.loc[dummy_index, :] = 0.0

    blank_column_trios = product(
        target_symbols,
        ("PRICE", "VOLUME", "ABSTRACT"),
        ("BLANK",),
    )
    new_indicators: dict[str, pd.Series] = {}
    base_index = candle_data.index
    for blank_column in ("/".join(t) for t in blank_column_trios):
        new_indicators[blank_column] = pd.Series(
            np.nan,
            index=base_index,
            dtype=np.float32,
        )

    input = IndicatorInput(
        target_symbols=target_symbols,
        candle_data=candle_data,
        new_indicators=new_indicators,
    )
    strategy.create_indicators(input)

    for column_name, new_indicator in new_indicators.items():
        # Validate the name format.
        if not isinstance(column_name, str):
            continue
        column_trio = column_name.split("/")
        if len(column_trio) != COLUMN_PARTS_COUNT:
            continue
        symbol, category, _ = column_trio
        if symbol not in target_symbols or category not in GRAPH_TYPES:
            continue
        # Validate the indicator format.
        if not isinstance(new_indicator, pd.Series):
            continue
        if not pd.api.types.is_numeric_dtype(new_indicator):
            continue
        # Convert each element into strings and make it into a name.
        new_indicator.name = column_name

    indicators = pd.concat(new_indicators.values(), axis="columns")
    indicators = indicators.astype(np.float32)

    indicators = indicators.iloc[:-1]

    if only_last_index:
        return indicators.tail(1)
    else:
        return indicators


def make_decisions(context: DecisionContext) -> dict[str, dict[OrderType, Decision]]:
    """Make trading decisions based on current market state."""
    new_decisions: dict[str, dict[OrderType, Decision]] = {}
    for symbol in context.target_symbols:
        new_decisions[symbol] = {}

    input = DecisionInput(
        target_symbols=context.target_symbols,
        account_state=context.account_state,
        current_moment=context.current_moment,
        current_candle_data=context.current_candle_data,
        current_indicators=context.current_indicators,
        scribbles=context.scribbles,
        new_decisions=new_decisions,
    )
    context.strategy.create_decisions(input)

    blank_symbols: list[str] = []
    for symbol, symbol_decisions in new_decisions.items():
        if len(symbol_decisions) == 0:
            blank_symbols.append(symbol)
    for blank_symbol in blank_symbols:
        new_decisions.pop(blank_symbol)

    return new_decisions


class SimulationError(Exception):
    pass


class OrderRole(Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class OrderHandlerResult(NamedTuple):
    """Result from order handler methods."""

    would_trade_happen: bool
    role: OrderRole
    fill_price: float
    amount_shift: float
    is_margin_negative: bool
    is_margin_nan: bool


class CalculationInput(NamedTuple):
    strategy: Strategy
    progress_list: ListProxy
    target_progress: int
    target_symbols: list[str]
    calculation_index: pd.DatetimeIndex
    chunk_candle_data: pd.DataFrame
    chunk_indicators: pd.DataFrame
    chunk_asset_record: pd.DataFrame
    chunk_unrealized_changes: pd.Series
    chunk_scribbles: dict[Any, Any]
    chunk_account_state: AccountState
    chunk_virtual_state: VirtualState


class CalculationOutput(NamedTuple):
    chunk_asset_record: pd.DataFrame
    chunk_unrealized_changes: pd.Series
    chunk_scribbles: dict[Any, Any]
    chunk_account_state: AccountState
    chunk_virtual_state: VirtualState


ORDER_ID_MIN, ORDER_ID_MAX = 10**18, 10**19 - 1


class ChunkSimulator:
    """
    Encapsulates the logic for simulating trading over a chunk of time.
    This class eliminates the need for multiple NamedTuples by using instance
    variables to hold state, making method signatures cleaner and reducing
    parameter passing overhead.
    """

    def __init__(self, calculation_input: CalculationInput):
        # Input parameters
        self.strategy = calculation_input.strategy
        self.progress_list = calculation_input.progress_list
        self.target_progress = calculation_input.target_progress
        self.target_symbols = calculation_input.target_symbols
        self.calculation_index = calculation_input.calculation_index

        # Chunk data (will be converted to arrays)
        self.chunk_candle_data = calculation_input.chunk_candle_data
        self.chunk_indicators = calculation_input.chunk_indicators
        self.chunk_asset_record = calculation_input.chunk_asset_record
        self.chunk_unrealized_changes = calculation_input.chunk_unrealized_changes

        # State that gets mutated
        self.chunk_scribbles = calculation_input.chunk_scribbles
        self.chunk_account_state = calculation_input.chunk_account_state
        self.chunk_virtual_state = calculation_input.chunk_virtual_state

        # Constants
        self.decision_lag = 3000  # milliseconds

        # Working arrays, initialized in `simulate` method
        self.candle_data_ar: np.recarray
        self.indicators_ar: np.recarray
        self.asset_record_ar: np.recarray
        self.chunk_unrealized_changes_ar: np.recarray
        self.cycle: int = 0

    def simulate(self) -> CalculationOutput:
        """Run the trading simulation."""
        if isinstance(self.strategy, SavedStrategy):
            self.strategy.compile_code()

        if len(self.calculation_index) == 0:
            return CalculationOutput(
                chunk_asset_record=self.chunk_asset_record,
                chunk_unrealized_changes=self.chunk_unrealized_changes,
                chunk_scribbles=self.chunk_scribbles,
                chunk_account_state=self.chunk_account_state,
                chunk_virtual_state=self.chunk_virtual_state,
            )

        # Convert DataFrames to numpy arrays for performance
        calculation_index_ar = self.calculation_index.to_numpy()
        self.candle_data_ar = self.chunk_candle_data.to_records()
        self.indicators_ar = self.chunk_indicators.to_records()
        self.asset_record_ar = self.chunk_asset_record.to_records()
        self.chunk_unrealized_changes_ar = (
            self.chunk_unrealized_changes.to_frame().to_records()
        )

        calculation_index_length = len(calculation_index_ar)
        first_calculation_moment = calculation_index_ar[0]

        # Main simulation loop
        for cycle in range(calculation_index_length):
            self.cycle = cycle
            before_moment = calculation_index_ar[cycle]
            current_moment = before_moment + timedelta(seconds=10)

            # Process all symbols
            for symbol in self.target_symbols:
                self._process_symbol(symbol, current_moment, before_moment)

            # Update unrealized changes
            self._update_unrealized_state(before_moment, current_moment)

            # Make new trading decisions
            self._process_decisions(current_moment)

            # Update progress
            self._update_progress(current_moment, first_calculation_moment)

        return self._create_output()

    def _process_symbol(
        self, symbol: str, current_moment: datetime, before_moment: datetime
    ) -> None:
        """Process orders and trades for a single symbol."""
        open_price = float(self.candle_data_ar[self.cycle][f"{symbol}/OPEN"])
        close_price = float(self.candle_data_ar[self.cycle][f"{symbol}/CLOSE"])

        if math.isnan(open_price) or math.isnan(close_price):
            return

        # Initialize trade state
        would_trade_happen = False
        amount_shift = 0.0
        fill_price = 0.0
        role: OrderRole | None = None
        price_speed = (close_price - open_price) / 10
        is_margin_negative = False
        is_margin_nan = False

        # Handle CANCEL_ALL
        if OrderType.CANCEL_ALL in self.chunk_virtual_state.placements[symbol]:
            self._handle_cancel_all(symbol)

        # Try each order type in priority order
        result = self._try_order_types(symbol, open_price, price_speed)
        if result:
            would_trade_happen = result.would_trade_happen
            role = result.role
            fill_price = result.fill_price
            amount_shift = result.amount_shift
            is_margin_negative = result.is_margin_negative
            is_margin_nan = result.is_margin_nan

        # Validate and execute trade
        if is_margin_negative:
            raise SimulationError(
                "Got an order with a negative margin "
                f"while calculating {symbol} market at {current_moment}"
            )
        if is_margin_nan:
            raise SimulationError(
                "Got an order with a non-numeric margin "
                f"while calculating {symbol} market at {current_moment}"
            )

        if would_trade_happen:
            self._execute_trade(
                symbol,
                TradeAmounts(amount_shift, fill_price),
                TradeMoments(current_moment, before_moment),
                open_price,
                role,
            )

        self._update_account_state_for_symbol(symbol)

    def _handle_cancel_all(self, symbol: str) -> None:
        """Cancel all pending orders for a symbol."""
        cancel_placement_names: list[OrderType] = []
        for order_type in self.chunk_virtual_state.placements[symbol].keys():
            if order_type.is_later() or order_type.is_book():
                cancel_placement_names.append(order_type)
        for cancel_placement_name in cancel_placement_names:
            self.chunk_virtual_state.placements[symbol].pop(cancel_placement_name)
        self.chunk_virtual_state.placements[symbol].pop(OrderType.CANCEL_ALL)

    def _try_order_types(
        self, symbol: str, open_price: float, price_speed: float
    ) -> OrderHandlerResult | None:
        """Try processing each order type, returning first match."""
        # NOW orders
        now_handlers = {
            OrderType.NOW_CLOSE: lambda: self._handle_now_close(
                symbol, open_price, price_speed
            ),
            OrderType.NOW_BUY: lambda: self._handle_now_buy(
                symbol, open_price, price_speed
            ),
            OrderType.NOW_SELL: lambda: self._handle_now_sell(
                symbol, open_price, price_speed
            ),
        }
        for order_type, handler in now_handlers.items():
            if order_type in self.chunk_virtual_state.placements[symbol]:
                result = handler()
                if result:
                    return result

        # LATER orders
        later_handlers = {
            OrderType.LATER_UP_CLOSE: lambda: self._handle_later_close(
                symbol, OrderType.LATER_UP_CLOSE
            ),
            OrderType.LATER_DOWN_CLOSE: lambda: self._handle_later_close(
                symbol, OrderType.LATER_DOWN_CLOSE
            ),
            OrderType.LATER_UP_BUY: lambda: self._handle_later_buy_sell(
                symbol, OrderType.LATER_UP_BUY, False
            ),
            OrderType.LATER_DOWN_BUY: lambda: self._handle_later_buy_sell(
                symbol, OrderType.LATER_DOWN_BUY, False
            ),
            OrderType.LATER_UP_SELL: lambda: self._handle_later_buy_sell(
                symbol, OrderType.LATER_UP_SELL, True
            ),
            OrderType.LATER_DOWN_SELL: lambda: self._handle_later_buy_sell(
                symbol, OrderType.LATER_DOWN_SELL, True
            ),
        }
        for order_type, handler in later_handlers.items():
            if order_type in self.chunk_virtual_state.placements[symbol]:
                result = handler()
                if result:
                    return result

        # BOOK orders
        book_handlers = {
            OrderType.BOOK_BUY: lambda: self._handle_book_order(
                symbol, OrderType.BOOK_BUY, False
            ),
            OrderType.BOOK_SELL: lambda: self._handle_book_order(
                symbol, OrderType.BOOK_SELL, True
            ),
        }
        for order_type, handler in book_handlers.items():
            if order_type in self.chunk_virtual_state.placements[symbol]:
                result = handler()
                if result:
                    return result

        return None

    def _handle_now_close(
        self, symbol: str, open_price: float, price_speed: float
    ) -> OrderHandlerResult:
        """Handle NOW_CLOSE order."""
        role = OrderRole.TAKER
        fill_price = open_price + price_speed * (self.decision_lag / 1000)
        amount_shift = -self.chunk_virtual_state.positions[symbol].amount
        self.chunk_virtual_state.placements[symbol].pop(OrderType.NOW_CLOSE)
        return OrderHandlerResult(True, role, fill_price, amount_shift, False, False)

    def _handle_now_buy(
        self, symbol: str, open_price: float, price_speed: float
    ) -> OrderHandlerResult:
        """Handle NOW_BUY order."""
        placement = self.chunk_virtual_state.placements[symbol][OrderType.NOW_BUY]
        role = OrderRole.TAKER
        fill_price = open_price + price_speed * (self.decision_lag / 1000)
        fill_margin = placement.margin
        is_margin_negative = fill_margin < 0.0
        is_margin_nan = math.isnan(fill_margin)
        amount_shift = fill_margin / fill_price
        self.chunk_virtual_state.placements[symbol].pop(OrderType.NOW_BUY)
        return OrderHandlerResult(
            True, role, fill_price, amount_shift, is_margin_negative, is_margin_nan
        )

    def _handle_now_sell(
        self, symbol: str, open_price: float, price_speed: float
    ) -> OrderHandlerResult:
        """Handle NOW_SELL order."""
        placement = self.chunk_virtual_state.placements[symbol][OrderType.NOW_SELL]
        role = OrderRole.TAKER
        fill_price = open_price + price_speed * (self.decision_lag / 1000)
        fill_margin = placement.margin
        is_margin_negative = fill_margin < 0.0
        is_margin_nan = math.isnan(fill_margin)
        amount_shift = -fill_margin / fill_price
        self.chunk_virtual_state.placements[symbol].pop(OrderType.NOW_SELL)
        return OrderHandlerResult(
            True, role, fill_price, amount_shift, is_margin_negative, is_margin_nan
        )

    def _handle_later_close(
        self, symbol: str, order_type: OrderType
    ) -> OrderHandlerResult | None:
        """Handle LATER_*_CLOSE orders."""
        placement = self.chunk_virtual_state.placements[symbol][order_type]
        boundary = placement.boundary
        wobble_high = float(self.candle_data_ar[self.cycle][f"{symbol}/HIGH"])
        wobble_low = float(self.candle_data_ar[self.cycle][f"{symbol}/LOW"])

        if wobble_low < boundary < wobble_high:
            role = OrderRole.TAKER
            fill_price = boundary
            amount_shift = -self.chunk_virtual_state.positions[symbol].amount
            self.chunk_virtual_state.placements[symbol].pop(order_type)
            return OrderHandlerResult(
                True, role, fill_price, amount_shift, False, False
            )
        return None

    def _handle_later_buy_sell(
        self, symbol: str, order_type: OrderType, is_sell: bool
    ) -> OrderHandlerResult | None:
        """Handle LATER_*_BUY/SELL orders."""
        placement = self.chunk_virtual_state.placements[symbol][order_type]
        boundary = placement.boundary
        wobble_high = float(self.candle_data_ar[self.cycle][f"{symbol}/HIGH"])
        wobble_low = float(self.candle_data_ar[self.cycle][f"{symbol}/LOW"])

        if wobble_low < boundary < wobble_high:
            role = OrderRole.TAKER
            fill_price = boundary
            fill_margin = placement.margin
            is_margin_negative = fill_margin < 0.0
            is_margin_nan = math.isnan(fill_margin)
            amount_shift = (-fill_margin if is_sell else fill_margin) / fill_price
            self.chunk_virtual_state.placements[symbol].pop(order_type)
            return OrderHandlerResult(
                True,
                role,
                fill_price,
                amount_shift,
                is_margin_negative,
                is_margin_nan,
            )
        return None

    def _handle_book_order(
        self, symbol: str, order_type: OrderType, is_sell: bool
    ) -> OrderHandlerResult | None:
        """Handle BOOK_BUY/SELL orders."""
        placement = self.chunk_virtual_state.placements[symbol][order_type]
        boundary = placement.boundary
        wobble_high = float(self.candle_data_ar[self.cycle][f"{symbol}/HIGH"])
        wobble_low = float(self.candle_data_ar[self.cycle][f"{symbol}/LOW"])

        if wobble_low < boundary < wobble_high:
            role = OrderRole.MAKER
            fill_price = boundary
            fill_margin = placement.margin
            is_margin_negative = fill_margin < 0.0
            is_margin_nan = math.isnan(fill_margin)
            amount_shift = (-fill_margin if is_sell else fill_margin) / fill_price
            self.chunk_virtual_state.placements[symbol].pop(order_type)
            return OrderHandlerResult(
                True,
                role,
                fill_price,
                amount_shift,
                is_margin_negative,
                is_margin_nan,
            )
        return None

    def _execute_trade(
        self,
        symbol: str,
        trade_amounts: TradeAmounts,
        moments: TradeMoments,
        open_price: float,
        role: OrderRole | None = None,
    ) -> None:
        """Execute a trade by updating positions and recording it."""
        amount_shift = trade_amounts.amount_shift
        fill_price = trade_amounts.fill_price
        current_moment = moments.current_moment
        before_moment = moments.before_moment
        virtual_position = self.chunk_virtual_state.positions[symbol]
        before_entry_price = virtual_position.entry_price
        before_amount = virtual_position.amount

        virtual_position.amount += amount_shift
        current_amount = virtual_position.amount

        # Update position entry price and balance based on trade type
        if before_amount == 0.0 and current_amount != 0.0:
            # Opening new position
            virtual_position.entry_price = fill_price
            invested_margin = abs(current_amount) * fill_price
            self.chunk_virtual_state.available_balance -= invested_margin
        elif before_amount != 0.0 and current_amount == 0.0:
            # Closing position
            virtual_position.entry_price = 0.0
            price_difference = fill_price - before_entry_price
            realized_profit = price_difference * before_amount
            returned_margin = abs(before_amount) * before_entry_price
            self.chunk_virtual_state.available_balance += (
                returned_margin + realized_profit
            )
        elif before_amount * current_amount < 0.0:
            # Reversing position
            virtual_position.entry_price = fill_price
            price_difference = fill_price - before_entry_price
            realized_profit = price_difference * before_amount
            returned_margin = abs(before_amount) * before_entry_price
            invested_margin = abs(current_amount) * fill_price
            self.chunk_virtual_state.available_balance += (
                returned_margin - invested_margin + realized_profit
            )
        elif abs(current_amount) > abs(before_amount):
            # Adding to position
            before_numerator = before_entry_price * before_amount
            new_numerator = fill_price * amount_shift
            current_numerator = before_numerator + new_numerator
            new_entry_price = current_numerator / current_amount
            virtual_position.entry_price = new_entry_price
            invested_margin = abs(amount_shift) * fill_price
            self.chunk_virtual_state.available_balance -= invested_margin
        else:
            # Reducing position
            virtual_position.entry_price = before_entry_price
            price_difference = fill_price - before_entry_price
            realized_profit = price_difference * (-amount_shift)
            returned_margin = abs(amount_shift) * before_entry_price
            self.chunk_virtual_state.available_balance += (
                returned_margin + realized_profit
            )

        if self.chunk_virtual_state.available_balance < 0.0:
            raise SimulationError(
                f"Available balance went below zero while calculating {symbol} market at {current_moment}"
            )

        # Record the trade
        if role is not None:
            self._record_trade(
                symbol,
                fill_price,
                role,
                TradeDetails(before_moment, amount_shift, open_price),
            )

    def _record_trade(
        self,
        symbol: str,
        fill_price: float,
        role: OrderRole,
        trade_details: TradeDetails,
    ) -> None:
        """Record a trade in the asset record."""
        before_moment = trade_details.before_moment
        amount_shift = trade_details.amount_shift
        open_price = trade_details.open_price
        fill_time = before_moment + timedelta(milliseconds=self.decision_lag)
        fill_time_np = np.datetime64(fill_time)
        while fill_time_np in self.asset_record_ar["index"]:
            fill_time_np += np.timedelta64(1, "ms")

        wallet_balance = self.chunk_virtual_state.available_balance
        for symbol_key, location in self.chunk_virtual_state.positions.items():
            if location.amount == 0.0:
                continue
            symbol_price = float(self.candle_data_ar[self.cycle][f"{symbol_key}/CLOSE"])
            if math.isnan(symbol_price):
                continue
            current_margin = abs(location.amount) * location.entry_price
            wallet_balance += current_margin

        margin_ratio = abs(amount_shift) * open_price / wallet_balance
        order_id = random.randint(ORDER_ID_MIN, ORDER_ID_MAX)

        if amount_shift == 0.0:
            raise ValueError("Amount of asset shift cannot be zero")
        if fill_price <= 0.0:
            raise ValueError("The fill price should be bigger than zero")

        original_size = self.asset_record_ar.shape[0]
        self.asset_record_ar.resize(original_size + 1)
        self.asset_record_ar[-1]["index"] = fill_time_np
        self.asset_record_ar[-1]["CAUSE"] = "AUTO_TRADE"
        self.asset_record_ar[-1]["SYMBOL"] = symbol
        self.asset_record_ar[-1]["SIDE"] = "BUY" if amount_shift > 0.0 else "SELL"
        self.asset_record_ar[-1]["FILL_PRICE"] = fill_price
        self.asset_record_ar[-1]["ROLE"] = role.value
        self.asset_record_ar[-1]["MARGIN_RATIO"] = margin_ratio
        self.asset_record_ar[-1]["ORDER_ID"] = order_id
        self.asset_record_ar[-1]["RESULT_ASSET"] = wallet_balance

        update_time = fill_time_np.astype(datetime).replace(tzinfo=timezone.utc)
        self.chunk_account_state.positions[symbol].update_time = update_time

    def _update_account_state_for_symbol(self, symbol: str) -> None:
        """Update account state for a specific symbol."""
        current_entry_price = self.chunk_virtual_state.positions[symbol].entry_price
        current_amount = self.chunk_virtual_state.positions[symbol].amount
        current_margin = abs(current_amount) * current_entry_price

        if current_amount > 0.0:
            current_direction = PositionDirection.LONG
        elif current_amount < 0.0:
            current_direction = PositionDirection.SHORT
        else:
            current_direction = PositionDirection.NONE

        symbol_position = Position(
            margin=current_margin,
            direction=current_direction,
            entry_price=current_entry_price,
            update_time=datetime.fromtimestamp(0.0),
        )
        self.chunk_account_state.positions[symbol] = symbol_position

        symbol_placements = self.chunk_virtual_state.placements[symbol]
        symbol_open_orders: dict[int, OpenOrder] = {}
        for order_type, placement in symbol_placements.items():
            symbol_open_orders[placement.order_id] = OpenOrder(
                order_type=order_type,
                boundary=placement.boundary,
                left_margin=placement.margin,
            )
        self.chunk_account_state.open_orders[symbol] = symbol_open_orders

    def _update_unrealized_state(
        self, before_moment: datetime, current_moment: datetime
    ) -> None:
        """Calculate and record unrealized profit/loss."""
        wallet_balance = self.chunk_virtual_state.available_balance
        unrealized_profit = 0.0

        for symbol_key, location in self.chunk_virtual_state.positions.items():
            if location.amount == 0.0:
                continue
            symbol_price = float(self.candle_data_ar[self.cycle][f"{symbol_key}/CLOSE"])
            if math.isnan(symbol_price):
                continue
            current_margin = abs(location.amount) * location.entry_price
            wallet_balance += current_margin

            # Assume mark price doesn't wobble more than 5%
            key_open_price = float(
                self.candle_data_ar[self.cycle][f"{symbol_key}/OPEN"]
            )
            key_close_price = float(
                self.candle_data_ar[self.cycle][f"{symbol_key}/CLOSE"]
            )
            if location.amount < 0.0:
                basic_price = max(key_open_price, key_close_price) * 1.05
                key_high_price = float(
                    self.candle_data_ar[self.cycle][f"{symbol_key}/HIGH"]
                )
                extreme_price = min(basic_price, key_high_price)
            else:
                basic_price = min(key_open_price, key_close_price) * 0.95
                key_low_price = float(
                    self.candle_data_ar[self.cycle][f"{symbol_key}/LOW"]
                )
                extreme_price = max(basic_price, key_low_price)
            price_difference = extreme_price - location.entry_price
            unrealized_profit += price_difference * location.amount

        unrealized_change = unrealized_profit / wallet_balance

        self.chunk_account_state.observed_until = current_moment
        self.chunk_account_state.wallet_balance = wallet_balance

        original_size = self.chunk_unrealized_changes_ar.shape[0]
        self.chunk_unrealized_changes_ar.resize(original_size + 1)
        self.chunk_unrealized_changes_ar[-1]["index"] = before_moment
        self.chunk_unrealized_changes_ar[-1]["0"] = unrealized_change

    def _process_decisions(self, current_moment: datetime) -> None:
        """Make trading decisions at cycle end."""
        record_row: np.record = self.candle_data_ar[self.cycle]
        current_candle_data = {
            k: float(record_row[k])
            for k in record_row.dtype.names or ()
            if k != "index"
        }
        record_row: np.record = self.indicators_ar[self.cycle]
        current_indicators = {
            k: float(record_row[k])
            for k in record_row.dtype.names or ()
            if k != "index"
        }

        decisions = make_decisions(
            DecisionContext(
                strategy=self.strategy,
                target_symbols=self.target_symbols,
                current_moment=current_moment,
                current_candle_data=current_candle_data,
                current_indicators=current_indicators,
                account_state=self.chunk_account_state.model_copy(deep=True),
                scribbles=self.chunk_scribbles,
            )
        )

        for symbol_key, symbol_decisions in decisions.items():
            for order_type, decision in symbol_decisions.items():
                placement = VirtualPlacement(
                    order_id=random.randint(ORDER_ID_MIN, ORDER_ID_MAX),
                    boundary=decision.boundary,
                    margin=decision.margin,
                )
                self.chunk_virtual_state.placements[symbol_key][order_type] = placement

    def _update_progress(
        self, current_moment: datetime, first_calculation_moment: datetime
    ) -> None:
        """Update progress reporting."""
        progress_in_time = current_moment - first_calculation_moment
        progress_in_seconds = progress_in_time.total_seconds()
        if progress_in_seconds % 3600 == 0.0:
            self.progress_list[self.target_progress] = max(progress_in_seconds, 0.0)

    def _create_output(self) -> CalculationOutput:
        """Convert arrays back to DataFrames and create output."""
        chunk_asset_record = pd.DataFrame(self.asset_record_ar)
        chunk_asset_record = chunk_asset_record.set_index("index")
        chunk_asset_record.index.name = None
        chunk_asset_record.index = pd.to_datetime(chunk_asset_record.index, utc=True)

        chunk_unrealized_changes_df = pd.DataFrame(self.chunk_unrealized_changes_ar)
        chunk_unrealized_changes_df = chunk_unrealized_changes_df.set_index("index")
        chunk_unrealized_changes_df.index.name = None
        chunk_unrealized_changes_df.index = pd.to_datetime(
            chunk_unrealized_changes_df.index, utc=True
        )
        chunk_unrealized_changes = chunk_unrealized_changes_df["0"]

        return CalculationOutput(
            chunk_asset_record=chunk_asset_record,
            chunk_unrealized_changes=chunk_unrealized_changes,
            chunk_scribbles=self.chunk_scribbles,
            chunk_account_state=self.chunk_account_state,
            chunk_virtual_state=self.chunk_virtual_state,
        )


def simulate_chunk(calculation_input: CalculationInput) -> CalculationOutput:
    """
    Simulates trading for a chunk of time.
    """
    simulator = ChunkSimulator(calculation_input)
    return simulator.simulate()
