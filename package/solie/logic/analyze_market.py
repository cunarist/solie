"""Market analysis and trading simulation logic."""

import math
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from itertools import product
from typing import Any, NamedTuple

import numpy as np
import polars as pl
from polars import DataFrame, Float32, Series

from solie.utility import (
    ASSET_RECORD_SCHEMA,
    COLUMN_PARTS_COUNT,
    AccountState,
    Decision,
    DecisionInput,
    IndicatorInput,
    OpenOrder,
    OrderType,
    Position,
    PositionDirection,
    Strategy,
    VirtualPlacement,
    VirtualPosition,
    VirtualState,
)

GRAPH_TYPES = ("PRICE", "VOLUME", "ABSTRACT")


def _append_indicator_dummy_row(candle_data: DataFrame) -> DataFrame:
    """Append one dummy row so rolling indicators keep their previous behavior."""
    if len(candle_data) == 0:
        return candle_data

    dummy_frame = candle_data.tail(1)
    expressions = [
        pl.lit(0).cast(candle_data.schema[column]).alias(column)
        for column in candle_data.columns
        if column != "timestamp"
    ]
    if "timestamp" in candle_data.columns:
        expressions.append((pl.col("timestamp") + 1000).alias("timestamp"))
    return candle_data.vstack(dummy_frame.with_columns(expressions))


def _blank_indicator_series(column_name: str, length: int) -> Series:
    """Create a blank numeric indicator series."""
    return Series(column_name, [np.nan] * length, dtype=Float32)


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
    candle_data: DataFrame,
    only_last_index: bool = False,
) -> DataFrame:
    """Calculate technical indicators using strategy's indicator script."""
    candle_data = candle_data.interpolate()
    candle_data = _append_indicator_dummy_row(candle_data)

    blank_column_trios = product(
        target_symbols,
        ("PRICE", "VOLUME", "ABSTRACT"),
        ("BLANK",),
    )
    new_indicators: dict[str, Series] = {}
    for blank_column in ("/".join(t) for t in blank_column_trios):
        new_indicators[blank_column] = _blank_indicator_series(
            blank_column,
            len(candle_data),
        )

    indicator_input = IndicatorInput(
        target_symbols=target_symbols,
        candle_data=candle_data,
        new_indicators=new_indicators,
    )
    strategy.create_indicators(indicator_input)

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
        if not isinstance(new_indicator, Series):
            continue
        if not new_indicator.dtype.is_numeric():
            continue
        # Convert each element into strings and make it into a name.
        new_indicators[column_name] = new_indicator.rename(column_name)

    indicators = DataFrame(new_indicators)
    indicators = indicators.cast(Float32)
    if "timestamp" in candle_data.columns:
        indicators = indicators.with_columns(timestamp=candle_data["timestamp"])

    indicators = indicators[:-1]

    if only_last_index:
        return indicators.tail(1)
    return indicators


def make_decisions(context: DecisionContext) -> dict[str, dict[OrderType, Decision]]:
    """Make trading decisions based on current market state."""
    new_decisions: dict[str, dict[OrderType, Decision]] = {}
    for symbol in context.target_symbols:
        new_decisions[symbol] = {}

    decision_input = DecisionInput(
        target_symbols=context.target_symbols,
        account_state=context.account_state,
        current_moment=context.current_moment,
        current_candle_data=context.current_candle_data,
        current_indicators=context.current_indicators,
        scribbles=context.scribbles,
        new_decisions=new_decisions,
    )
    context.strategy.create_decisions(decision_input)

    blank_symbols: list[str] = []
    for symbol, symbol_decisions in new_decisions.items():
        if len(symbol_decisions) == 0:
            blank_symbols.append(symbol)
    for blank_symbol in blank_symbols:
        new_decisions.pop(blank_symbol)

    return new_decisions


class SimulationError(Exception):
    """Exception raised during trading simulation."""


class OrderRole(Enum):
    """Role of trader in order execution."""

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


class SimulationState(NamedTuple):
    """Mutable simulation state carried between orchestration and execution."""

    asset_record: DataFrame
    unrealized_changes: Series
    scribbles: dict[Any, Any]
    account_state: AccountState
    virtual_state: VirtualState


class SimulationOutput(NamedTuple):
    """Output state from simulation calculation."""

    asset_record: DataFrame
    unrealized_changes: Series
    scribbles: dict[Any, Any]
    account_state: AccountState


ORDER_ID_MIN = 10**18
ORDER_ID_MAX = 2**63 - 1


class ChunkSimulation:
    """Sequential trading simulation state."""

    def __init__(
        self,
        *,
        strategy: Strategy,
        target_symbols: list[str],
        state: SimulationState,
    ) -> None:
        """Initialize reusable simulation state."""
        self.strategy = strategy
        self.target_symbols = target_symbols
        self.scribbles = state.scribbles
        self.account_state = state.account_state
        self.virtual_state = state.virtual_state
        self.decision_lag = 3000

        self.current_candle_data: dict[str, float] = {}
        self.asset_record_rows = [
            dict(row) for row in state.asset_record.iter_rows(named=True)
        ]
        self.asset_record_timestamps = {
            int(row["timestamp"])
            for row in self.asset_record_rows
            if isinstance(row.get("timestamp"), int | float)
        }
        self.unrealized_change_values = [
            float(value)
            for value in state.unrealized_changes
            if isinstance(value, int | float)
        ]

    def simulate_moment(
        self,
        *,
        timestamp: int,
        active_symbols: list[str],
        current_candle_data: dict[str, float],
        current_indicators: dict[str, float],
    ) -> None:
        """Simulate one candle timestamp for symbols that have a row."""
        if len(active_symbols) == 0:
            return

        before_moment = datetime.fromtimestamp(timestamp / 1000, UTC)
        current_moment = before_moment + timedelta(seconds=10)
        self.current_candle_data = current_candle_data

        for symbol in active_symbols:
            self._ensure_symbol(symbol)
            self._process_symbol(symbol, current_moment, before_moment)

        self._update_unrealized_state(current_moment)
        self._process_decisions(
            current_moment,
            current_candle_data,
            current_indicators,
        )

    def _ensure_symbol(self, symbol: str) -> None:
        """Ensure runtime account dictionaries contain a symbol."""
        if symbol not in self.virtual_state.positions:
            self.virtual_state.positions[symbol] = VirtualPosition(
                amount=0.0,
                entry_price=0.0,
            )
        if symbol not in self.virtual_state.placements:
            self.virtual_state.placements[symbol] = {}
        if symbol not in self.account_state.positions:
            self.account_state.positions[symbol] = Position(
                margin=0.0,
                direction=PositionDirection.NONE,
                entry_price=0.0,
                update_time=datetime.fromtimestamp(0.0, tz=UTC),
            )
        if symbol not in self.account_state.open_orders:
            self.account_state.open_orders[symbol] = {}

    def _candle_value(self, symbol: str, field: str) -> float:
        return self.current_candle_data.get(f"{symbol}/{field}", math.nan)

    def _process_symbol(
        self,
        symbol: str,
        current_moment: datetime,
        before_moment: datetime,
    ) -> None:
        """Process orders and trades for a single symbol."""
        open_price = self._candle_value(symbol, "OPEN")
        close_price = self._candle_value(symbol, "CLOSE")

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
        if OrderType.CANCEL_ALL in self.virtual_state.placements[symbol]:
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
            msg = (
                "Got an order with a negative margin "
                f"while calculating {symbol} market at {current_moment}"
            )
            raise SimulationError(
                msg,
            )
        if is_margin_nan:
            msg = (
                "Got an order with a non-numeric margin "
                f"while calculating {symbol} market at {current_moment}"
            )
            raise SimulationError(
                msg,
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
        cancel_placement_names = [
            order_type
            for order_type in self.virtual_state.placements[symbol]
            if order_type.is_later() or order_type.is_book()
        ]
        for cancel_placement_name in cancel_placement_names:
            self.virtual_state.placements[symbol].pop(cancel_placement_name)
        self.virtual_state.placements[symbol].pop(OrderType.CANCEL_ALL)

    def _try_order_types(
        self,
        symbol: str,
        open_price: float,
        price_speed: float,
    ) -> OrderHandlerResult | None:
        """Try processing each order type, returning first match."""
        # NOW orders
        now_handlers = {
            OrderType.NOW_CLOSE: lambda: self._handle_now_close(
                symbol,
                open_price,
                price_speed,
            ),
            OrderType.NOW_BUY: lambda: self._handle_now_buy(
                symbol,
                open_price,
                price_speed,
            ),
            OrderType.NOW_SELL: lambda: self._handle_now_sell(
                symbol,
                open_price,
                price_speed,
            ),
        }
        for order_type, handler in now_handlers.items():
            if order_type in self.virtual_state.placements[symbol]:
                result = handler()
                if result:
                    return result

        # LATER orders
        later_handlers = {
            OrderType.LATER_UP_CLOSE: lambda: self._handle_later_close(
                symbol,
                OrderType.LATER_UP_CLOSE,
            ),
            OrderType.LATER_DOWN_CLOSE: lambda: self._handle_later_close(
                symbol,
                OrderType.LATER_DOWN_CLOSE,
            ),
            OrderType.LATER_UP_BUY: lambda: self._handle_later_buy_sell(
                symbol,
                OrderType.LATER_UP_BUY,
                False,
            ),
            OrderType.LATER_DOWN_BUY: lambda: self._handle_later_buy_sell(
                symbol,
                OrderType.LATER_DOWN_BUY,
                False,
            ),
            OrderType.LATER_UP_SELL: lambda: self._handle_later_buy_sell(
                symbol,
                OrderType.LATER_UP_SELL,
                True,
            ),
            OrderType.LATER_DOWN_SELL: lambda: self._handle_later_buy_sell(
                symbol,
                OrderType.LATER_DOWN_SELL,
                True,
            ),
        }
        for order_type, handler in later_handlers.items():
            if order_type in self.virtual_state.placements[symbol]:
                result = handler()
                if result:
                    return result

        # BOOK orders
        book_handlers = {
            OrderType.BOOK_BUY: lambda: self._handle_book_order(
                symbol,
                OrderType.BOOK_BUY,
                False,
            ),
            OrderType.BOOK_SELL: lambda: self._handle_book_order(
                symbol,
                OrderType.BOOK_SELL,
                True,
            ),
        }
        for order_type, handler in book_handlers.items():
            if order_type in self.virtual_state.placements[symbol]:
                result = handler()
                if result:
                    return result

        return None

    def _handle_now_close(
        self,
        symbol: str,
        open_price: float,
        price_speed: float,
    ) -> OrderHandlerResult:
        """Handle NOW_CLOSE order."""
        role = OrderRole.TAKER
        fill_price = open_price + price_speed * (self.decision_lag / 1000)
        amount_shift = -self.virtual_state.positions[symbol].amount
        self.virtual_state.placements[symbol].pop(OrderType.NOW_CLOSE)
        return OrderHandlerResult(True, role, fill_price, amount_shift, False, False)

    def _handle_now_buy(
        self,
        symbol: str,
        open_price: float,
        price_speed: float,
    ) -> OrderHandlerResult:
        """Handle NOW_BUY order."""
        placement = self.virtual_state.placements[symbol][OrderType.NOW_BUY]
        role = OrderRole.TAKER
        fill_price = open_price + price_speed * (self.decision_lag / 1000)
        fill_margin = placement.margin
        is_margin_negative = fill_margin < 0.0
        is_margin_nan = math.isnan(fill_margin)
        amount_shift = fill_margin / fill_price
        self.virtual_state.placements[symbol].pop(OrderType.NOW_BUY)
        return OrderHandlerResult(
            True,
            role,
            fill_price,
            amount_shift,
            is_margin_negative,
            is_margin_nan,
        )

    def _handle_now_sell(
        self,
        symbol: str,
        open_price: float,
        price_speed: float,
    ) -> OrderHandlerResult:
        """Handle NOW_SELL order."""
        placement = self.virtual_state.placements[symbol][OrderType.NOW_SELL]
        role = OrderRole.TAKER
        fill_price = open_price + price_speed * (self.decision_lag / 1000)
        fill_margin = placement.margin
        is_margin_negative = fill_margin < 0.0
        is_margin_nan = math.isnan(fill_margin)
        amount_shift = -fill_margin / fill_price
        self.virtual_state.placements[symbol].pop(OrderType.NOW_SELL)
        return OrderHandlerResult(
            True,
            role,
            fill_price,
            amount_shift,
            is_margin_negative,
            is_margin_nan,
        )

    def _handle_later_close(
        self,
        symbol: str,
        order_type: OrderType,
    ) -> OrderHandlerResult | None:
        """Handle LATER_*_CLOSE orders."""
        placement = self.virtual_state.placements[symbol][order_type]
        boundary = placement.boundary
        wobble_high = self._candle_value(symbol, "HIGH")
        wobble_low = self._candle_value(symbol, "LOW")

        if wobble_low < boundary < wobble_high:
            role = OrderRole.TAKER
            fill_price = boundary
            amount_shift = -self.virtual_state.positions[symbol].amount
            self.virtual_state.placements[symbol].pop(order_type)
            return OrderHandlerResult(
                True,
                role,
                fill_price,
                amount_shift,
                False,
                False,
            )
        return None

    def _handle_later_buy_sell(
        self,
        symbol: str,
        order_type: OrderType,
        is_sell: bool,
    ) -> OrderHandlerResult | None:
        """Handle LATER_*_BUY/SELL orders."""
        placement = self.virtual_state.placements[symbol][order_type]
        boundary = placement.boundary
        wobble_high = self._candle_value(symbol, "HIGH")
        wobble_low = self._candle_value(symbol, "LOW")

        if wobble_low < boundary < wobble_high:
            role = OrderRole.TAKER
            fill_price = boundary
            fill_margin = placement.margin
            is_margin_negative = fill_margin < 0.0
            is_margin_nan = math.isnan(fill_margin)
            amount_shift = (-fill_margin if is_sell else fill_margin) / fill_price
            self.virtual_state.placements[symbol].pop(order_type)
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
        self,
        symbol: str,
        order_type: OrderType,
        is_sell: bool,
    ) -> OrderHandlerResult | None:
        """Handle BOOK_BUY/SELL orders."""
        placement = self.virtual_state.placements[symbol][order_type]
        boundary = placement.boundary
        wobble_high = self._candle_value(symbol, "HIGH")
        wobble_low = self._candle_value(symbol, "LOW")

        if wobble_low < boundary < wobble_high:
            role = OrderRole.MAKER
            fill_price = boundary
            fill_margin = placement.margin
            is_margin_negative = fill_margin < 0.0
            is_margin_nan = math.isnan(fill_margin)
            amount_shift = (-fill_margin if is_sell else fill_margin) / fill_price
            self.virtual_state.placements[symbol].pop(order_type)
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
        virtual_position = self.virtual_state.positions[symbol]
        before_entry_price = virtual_position.entry_price
        before_amount = virtual_position.amount

        virtual_position.amount += amount_shift
        current_amount = virtual_position.amount

        # Update position entry price and balance based on trade type
        if before_amount == 0.0 and current_amount != 0.0:
            # Opening new position
            virtual_position.entry_price = fill_price
            invested_margin = abs(current_amount) * fill_price
            self.virtual_state.available_balance -= invested_margin
        elif before_amount != 0.0 and current_amount == 0.0:
            # Closing position
            virtual_position.entry_price = 0.0
            price_difference = fill_price - before_entry_price
            realized_profit = price_difference * before_amount
            returned_margin = abs(before_amount) * before_entry_price
            self.virtual_state.available_balance += (
                returned_margin + realized_profit
            )
        elif before_amount * current_amount < 0.0:
            # Reversing position
            virtual_position.entry_price = fill_price
            price_difference = fill_price - before_entry_price
            realized_profit = price_difference * before_amount
            returned_margin = abs(before_amount) * before_entry_price
            invested_margin = abs(current_amount) * fill_price
            self.virtual_state.available_balance += (
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
            self.virtual_state.available_balance -= invested_margin
        else:
            # Reducing position
            virtual_position.entry_price = before_entry_price
            price_difference = fill_price - before_entry_price
            realized_profit = price_difference * (-amount_shift)
            returned_margin = abs(amount_shift) * before_entry_price
            self.virtual_state.available_balance += (
                returned_margin + realized_profit
            )

        if self.virtual_state.available_balance < 0.0:
            msg = (
                f"Available balance went below zero while calculating "
                f"{symbol} market at {current_moment}"
            )
            raise SimulationError(msg)

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
        fill_timestamp = int(fill_time.timestamp() * 1000)
        while fill_timestamp in self.asset_record_timestamps:
            fill_timestamp += 1

        wallet_balance = self.virtual_state.available_balance
        for location in self.virtual_state.positions.values():
            if location.amount == 0.0:
                continue
            current_margin = abs(location.amount) * location.entry_price
            wallet_balance += current_margin

        margin_ratio = abs(amount_shift) * open_price / wallet_balance
        order_id = ORDER_ID_MIN + secrets.randbelow(ORDER_ID_MAX - ORDER_ID_MIN + 1)

        if amount_shift == 0.0:
            msg = "Amount of asset shift cannot be zero"
            raise ValueError(msg)
        if fill_price <= 0.0:
            msg = "The fill price should be bigger than zero"
            raise ValueError(msg)

        self.asset_record_rows.append(
            {
                "timestamp": fill_timestamp,
                "CAUSE": "AUTO_TRADE",
                "SYMBOL": symbol,
                "SIDE": "BUY" if amount_shift > 0.0 else "SELL",
                "FILL_PRICE": fill_price,
                "ROLE": role.value,
                "MARGIN_RATIO": margin_ratio,
                "ORDER_ID": order_id,
                "RESULT_ASSET": wallet_balance,
            },
        )
        self.asset_record_timestamps.add(fill_timestamp)

        update_time = datetime.fromtimestamp(fill_timestamp / 1000, tz=UTC)
        self.account_state.positions[symbol].update_time = update_time

    def _update_account_state_for_symbol(self, symbol: str) -> None:
        """Update account state for a specific symbol."""
        current_entry_price = self.virtual_state.positions[symbol].entry_price
        current_amount = self.virtual_state.positions[symbol].amount
        current_margin = abs(current_amount) * current_entry_price

        if current_amount > 0.0:
            current_direction = PositionDirection.LONG
        elif current_amount < 0.0:
            current_direction = PositionDirection.SHORT
        else:
            current_direction = PositionDirection.NONE

        before_position = self.account_state.positions[symbol]
        symbol_position = Position(
            margin=current_margin,
            direction=current_direction,
            entry_price=current_entry_price,
            update_time=before_position.update_time,
        )
        self.account_state.positions[symbol] = symbol_position

        symbol_placements = self.virtual_state.placements[symbol]
        symbol_open_orders: dict[int, OpenOrder] = {}
        for order_type, placement in symbol_placements.items():
            symbol_open_orders[placement.order_id] = OpenOrder(
                order_type=order_type,
                boundary=placement.boundary,
                left_margin=placement.margin,
            )
        self.account_state.open_orders[symbol] = symbol_open_orders

    def _update_unrealized_state(
        self,
        current_moment: datetime,
    ) -> None:
        """Calculate and record unrealized profit/loss."""
        wallet_balance = self.virtual_state.available_balance
        unrealized_profit = 0.0

        for symbol_key, location in self.virtual_state.positions.items():
            if location.amount == 0.0:
                continue
            current_margin = abs(location.amount) * location.entry_price
            wallet_balance += current_margin
            symbol_price = self._candle_value(symbol_key, "CLOSE")
            if math.isnan(symbol_price):
                continue

            # Assume mark price doesn't wobble more than 5%
            key_open_price = self._candle_value(symbol_key, "OPEN")
            key_close_price = self._candle_value(symbol_key, "CLOSE")
            if location.amount < 0.0:
                basic_price = max(key_open_price, key_close_price) * 1.05
                key_high_price = self._candle_value(symbol_key, "HIGH")
                extreme_price = min(basic_price, key_high_price)
            else:
                basic_price = min(key_open_price, key_close_price) * 0.95
                key_low_price = self._candle_value(symbol_key, "LOW")
                extreme_price = max(basic_price, key_low_price)
            price_difference = extreme_price - location.entry_price
            unrealized_profit += price_difference * location.amount

        unrealized_change = unrealized_profit / wallet_balance

        self.account_state.observed_until = current_moment
        self.account_state.wallet_balance = wallet_balance

        self.unrealized_change_values.append(unrealized_change)

    def _process_decisions(
        self,
        current_moment: datetime,
        current_candle_data: dict[str, float],
        current_indicators: dict[str, float],
    ) -> None:
        """Make trading decisions at cycle end."""
        decisions = make_decisions(
            DecisionContext(
                strategy=self.strategy,
                target_symbols=self.target_symbols,
                current_moment=current_moment,
                current_candle_data=current_candle_data,
                current_indicators=current_indicators,
                account_state=self.account_state.model_copy(deep=True),
                scribbles=self.scribbles,
            ),
        )

        for symbol_key, symbol_decisions in decisions.items():
            self._ensure_symbol(symbol_key)
            for order_type, decision in symbol_decisions.items():
                placement = VirtualPlacement(
                    order_id=ORDER_ID_MIN
                    + secrets.randbelow(ORDER_ID_MAX - ORDER_ID_MIN + 1),
                    boundary=decision.boundary,
                    margin=decision.margin,
                )
                self.virtual_state.placements[symbol_key][order_type] = placement

    def finish(self) -> SimulationOutput:
        """Return the accumulated simulation state."""
        if len(self.asset_record_rows) == 0:
            asset_record = DataFrame(schema=ASSET_RECORD_SCHEMA)
        else:
            asset_record = DataFrame(
                self.asset_record_rows,
                schema=ASSET_RECORD_SCHEMA,
            ).sort("timestamp")
        unrealized_changes = Series(
            "0",
            self.unrealized_change_values,
            dtype=Float32,
        )
        return SimulationOutput(
            asset_record=asset_record,
            unrealized_changes=unrealized_changes,
            scribbles=self.scribbles,
            account_state=self.account_state,
        )
