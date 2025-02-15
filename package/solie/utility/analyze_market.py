import math
import random
from datetime import datetime, timedelta, timezone
from enum import Enum
from itertools import product
from multiprocessing.managers import ListProxy
from types import CodeType
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from .data_models import (
    AccountState,
    Decision,
    OpenOrder,
    OrderType,
    Position,
    PositionDirection,
    VirtualPlacement,
    VirtualState,
)

GRAPH_TYPES = ["PRICE", "VOLUME", "ABSTRACT"]


def make_indicators(
    target_symbols: list[str],
    candle_data: pd.DataFrame,
    indicators_script: str | CodeType,
    only_last_index: bool = False,
) -> pd.DataFrame:
    # ■■■■■ interpolate nans ■■■■■

    candle_data = candle_data.interpolate()  # type:ignore

    # ■■■■■ make dummy row to avoid ta error with all nan series ■■■■■

    if len(candle_data) > 0:
        dummy_index = candle_data.index[-1] + timedelta(seconds=1)  # type:ignore
    else:
        dummy_index = datetime.fromtimestamp(0, tz=timezone.utc)

    candle_data.loc[dummy_index, :] = 0.0

    # ■■■■■ basic values ■■■■■

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

    # ■■■■■ make individual indicators ■■■■■

    namespace = {
        "target_symbols": target_symbols,
        "candle_data": candle_data,
        "new_indicators": new_indicators,
    }
    exec(indicators_script, namespace)

    # ■■■■■ concatenate individual indicators into one ■■■■■

    for column_name, new_indicator in new_indicators.items():
        # Validate the name format.
        if not isinstance(column_name, str):
            continue
        column_trio = column_name.split("/")
        symbol, category, _ = column_trio
        if symbol not in target_symbols or category not in GRAPH_TYPES:
            continue
        # Validate the indicator format.
        if not isinstance(new_indicator, pd.Series):
            continue
        # Convert each element into strings and make it into a name.
        new_indicator.name = column_name

    indicators = pd.concat(new_indicators.values(), axis="columns")
    indicators = indicators.astype(np.float32)

    # ■■■■■ remove dummy row ■■■■■

    indicators = indicators.iloc[:-1]

    if only_last_index:
        return indicators.tail(1)
    else:
        return indicators


def decide(
    target_symbols: list[str],
    current_moment: datetime,
    current_candle_data: dict[str, float],
    current_indicators: dict[str, float],
    account_state: AccountState,
    scribbles: dict[Any, Any],
    decision_script: str | CodeType,
) -> dict[str, dict[OrderType, Decision]]:
    # ■■■■■ decision template ■■■■■

    decisions: dict[str, dict[OrderType, Decision]] = {}
    for symbol in target_symbols:
        decisions[symbol] = {}

    # ■■■■■ write decisions ■■■■■

    namespace = {
        "target_symbols": target_symbols,
        "current_moment": current_moment,
        "current_candle_data": current_candle_data,
        "current_indicators": current_indicators,
        "account_state": account_state,
        "scribbles": scribbles,
        "decisions": decisions,
    }

    exec(decision_script, namespace)

    # ■■■■■ return decision ■■■■■

    blank_symbols: list[str] = []
    for symbol, symbol_decisions in decisions.items():
        if len(symbol_decisions) == 0:
            blank_symbols.append(symbol)
    for blank_symbol in blank_symbols:
        decisions.pop(blank_symbol)

    return decisions


class SimulationError(Exception):
    pass


class OrderRole(Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class CalculationInput(NamedTuple):
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
    decision_script: str


class CalculationOutput(NamedTuple):
    chunk_asset_record: pd.DataFrame
    chunk_unrealized_changes: pd.Series
    chunk_scribbles: dict[Any, Any]
    chunk_account_state: AccountState
    chunk_virtual_state: VirtualState


ORDER_ID_MIN, ORDER_ID_MAX = 10**18, 10**19 - 1


def simulate_chunk(calculation_input: CalculationInput) -> CalculationOutput:
    # leverage is treated as 1
    # because those are going to be applied at the presentation phase

    # ■■■■■ get data ■■■■■

    progress_list = calculation_input.progress_list
    target_progress = calculation_input.target_progress
    target_symbols = calculation_input.target_symbols
    calculation_index = calculation_input.calculation_index
    chunk_candle_data = calculation_input.chunk_candle_data
    chunk_indicators = calculation_input.chunk_indicators
    chunk_asset_record = calculation_input.chunk_asset_record
    chunk_unrealized_changes = calculation_input.chunk_unrealized_changes
    chunk_scribbles = calculation_input.chunk_scribbles
    chunk_account_state = calculation_input.chunk_account_state
    chunk_virtual_state = calculation_input.chunk_virtual_state
    decision_script = calculation_input.decision_script

    # ■■■■■ basic values ■■■■■

    decision_lag = 3000  # milliseconds

    # ■■■■■ return blank data if there's nothing to calculate ■■■■■

    if len(calculation_index) == 0:
        calculation_output = CalculationOutput(
            chunk_asset_record=chunk_asset_record,
            chunk_unrealized_changes=chunk_unrealized_changes,
            chunk_scribbles=chunk_scribbles,
            chunk_account_state=chunk_account_state,
            chunk_virtual_state=chunk_virtual_state,
        )
        return calculation_output

    # ■■■■■ convert to numpy objects for fast calculation ■■■■■

    calculation_index_ar = calculation_index.to_numpy()  # inside are datetime objects
    candle_data_ar = chunk_candle_data.to_records()
    indicators_ar = chunk_indicators.to_records()
    asset_record_ar = chunk_asset_record.to_records()
    chunk_unrealized_changes_ar = chunk_unrealized_changes.to_frame().to_records()

    # ■■■■■ actual loop calculation ■■■■■

    calculation_index_length = len(calculation_index_ar)
    decision_script_compiled = compile(decision_script, "<string>", "exec")
    first_calculation_moment = calculation_index_ar[0]

    for cycle in range(calculation_index_length):
        before_moment = calculation_index_ar[cycle]
        current_moment = before_moment + timedelta(seconds=10)

        for symbol in target_symbols:
            # ■■■■■ basic variables ■■■■■

            open_price = candle_data_ar[cycle][f"{symbol}/OPEN"]
            close_price = candle_data_ar[cycle][f"{symbol}/CLOSE"]
            if math.isnan(open_price) or math.isnan(close_price):
                continue

            would_trade_happen = False
            is_new_trade_found = False
            amount_shift = 0
            fill_price = 0
            role: OrderRole | None = None

            # ■■■■■ check if any order would be filled ■■■■■

            price_speed = (close_price - open_price) / 10
            is_margin_negative = False
            is_margin_nan = False

            # special placements
            if OrderType.CANCEL_ALL in chunk_virtual_state.placements[symbol]:
                cancel_placement_names = []
                for order_type in chunk_virtual_state.placements[symbol].keys():
                    if order_type.is_later() or order_type.is_book():
                        cancel_placement_names.append(order_type)
                for cancel_placement_name in cancel_placement_names:
                    chunk_virtual_state.placements[symbol].pop(cancel_placement_name)
                chunk_virtual_state.placements[symbol].pop(OrderType.CANCEL_ALL)

            # instant placements
            if OrderType.NOW_CLOSE in chunk_virtual_state.placements[symbol]:
                would_trade_happen = True
                placement = chunk_virtual_state.placements[symbol][OrderType.NOW_CLOSE]
                role = OrderRole.TAKER
                fill_price = open_price + price_speed * (decision_lag / 1000)
                amount_shift = -chunk_virtual_state.positions[symbol].amount
                chunk_virtual_state.placements[symbol].pop(OrderType.NOW_CLOSE)

            if OrderType.NOW_BUY in chunk_virtual_state.placements[symbol]:
                would_trade_happen = True
                placement = chunk_virtual_state.placements[symbol][OrderType.NOW_BUY]
                role = OrderRole.TAKER
                fill_price = open_price + price_speed * (decision_lag / 1000)
                fill_margin = placement.margin
                if fill_margin < 0:
                    is_margin_negative = True
                if math.isnan(fill_margin):
                    is_margin_nan = True
                amount_shift = fill_margin / fill_price
                chunk_virtual_state.placements[symbol].pop(OrderType.NOW_BUY)

            if OrderType.NOW_SELL in chunk_virtual_state.placements[symbol]:
                would_trade_happen = True
                placement = chunk_virtual_state.placements[symbol][OrderType.NOW_SELL]
                role = OrderRole.TAKER
                fill_price = open_price + price_speed * (decision_lag / 1000)
                fill_margin = placement.margin
                if fill_margin < 0:
                    is_margin_negative = True
                if math.isnan(fill_margin):
                    is_margin_nan = True
                amount_shift = -fill_margin / fill_price
                chunk_virtual_state.placements[symbol].pop(OrderType.NOW_SELL)

            # conditional placements
            if OrderType.LATER_UP_CLOSE in chunk_virtual_state.placements[symbol]:
                placement = chunk_virtual_state.placements[symbol][
                    OrderType.LATER_UP_CLOSE
                ]
                boundary = placement.boundary

                wobble_high = candle_data_ar[cycle][f"{symbol}/HIGH"]
                wobble_low = candle_data_ar[cycle][f"{symbol}/LOW"]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = OrderRole.TAKER
                    fill_price = boundary
                    amount_shift = -chunk_virtual_state.positions[symbol].amount
                    chunk_virtual_state.placements[symbol].pop(OrderType.LATER_UP_CLOSE)

            if OrderType.LATER_DOWN_CLOSE in chunk_virtual_state.placements[symbol]:
                placement = chunk_virtual_state.placements[symbol][
                    OrderType.LATER_DOWN_CLOSE
                ]
                boundary = placement.boundary

                wobble_high = candle_data_ar[cycle][f"{symbol}/HIGH"]
                wobble_low = candle_data_ar[cycle][f"{symbol}/LOW"]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = OrderRole.TAKER
                    fill_price = boundary
                    amount_shift = -chunk_virtual_state.positions[symbol].amount
                    chunk_virtual_state.placements[symbol].pop(
                        OrderType.LATER_DOWN_CLOSE
                    )

            if OrderType.LATER_UP_BUY in chunk_virtual_state.placements[symbol]:
                placement = chunk_virtual_state.placements[symbol][
                    OrderType.LATER_UP_BUY
                ]
                boundary = placement.boundary

                wobble_high = candle_data_ar[cycle][f"{symbol}/HIGH"]
                wobble_low = candle_data_ar[cycle][f"{symbol}/LOW"]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = OrderRole.TAKER
                    fill_price = boundary
                    fill_margin = placement.margin
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = fill_margin / fill_price
                    chunk_virtual_state.placements[symbol].pop(OrderType.LATER_UP_BUY)

            if OrderType.LATER_DOWN_BUY in chunk_virtual_state.placements[symbol]:
                placement = chunk_virtual_state.placements[symbol][
                    OrderType.LATER_DOWN_BUY
                ]
                boundary = placement.boundary

                wobble_high = candle_data_ar[cycle][f"{symbol}/HIGH"]
                wobble_low = candle_data_ar[cycle][f"{symbol}/LOW"]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = OrderRole.TAKER
                    fill_price = boundary
                    fill_margin = placement.margin
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = fill_margin / fill_price
                    chunk_virtual_state.placements[symbol].pop(OrderType.LATER_DOWN_BUY)

            if OrderType.LATER_UP_SELL in chunk_virtual_state.placements[symbol]:
                placement = chunk_virtual_state.placements[symbol][
                    OrderType.LATER_UP_SELL
                ]
                boundary = placement.boundary

                wobble_high = candle_data_ar[cycle][f"{symbol}/HIGH"]
                wobble_low = candle_data_ar[cycle][f"{symbol}/LOW"]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = OrderRole.TAKER
                    fill_price = boundary
                    fill_margin = placement.margin
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = -fill_margin / fill_price
                    chunk_virtual_state.placements[symbol].pop(OrderType.LATER_UP_SELL)

            if OrderType.LATER_DOWN_SELL in chunk_virtual_state.placements[symbol]:
                placement = chunk_virtual_state.placements[symbol][
                    OrderType.LATER_DOWN_SELL
                ]
                boundary = placement.boundary

                wobble_high = candle_data_ar[cycle][f"{symbol}/HIGH"]
                wobble_low = candle_data_ar[cycle][f"{symbol}/LOW"]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = OrderRole.TAKER
                    fill_price = boundary
                    fill_margin = placement.margin
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = -fill_margin / fill_price
                    chunk_virtual_state.placements[symbol].pop(
                        OrderType.LATER_DOWN_SELL
                    )

            if OrderType.BOOK_BUY in chunk_virtual_state.placements[symbol]:
                placement = chunk_virtual_state.placements[symbol][OrderType.BOOK_BUY]
                boundary = placement.boundary

                wobble_high = candle_data_ar[cycle][f"{symbol}/HIGH"]
                wobble_low = candle_data_ar[cycle][f"{symbol}/LOW"]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = OrderRole.MAKER
                    fill_price = boundary
                    fill_margin = placement.margin
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = fill_margin / fill_price
                    chunk_virtual_state.placements[symbol].pop(OrderType.BOOK_BUY)

            if OrderType.BOOK_SELL in chunk_virtual_state.placements[symbol]:
                placement = chunk_virtual_state.placements[symbol][OrderType.BOOK_SELL]
                boundary = placement.boundary

                wobble_high = candle_data_ar[cycle][f"{symbol}/HIGH"]
                wobble_low = candle_data_ar[cycle][f"{symbol}/LOW"]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = OrderRole.MAKER
                    fill_price = boundary
                    fill_margin = placement.margin
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = -fill_margin / fill_price
                    chunk_virtual_state.placements[symbol].pop(OrderType.BOOK_SELL)

            # check if situation is okay
            if is_margin_negative:
                text = ""
                text += "Got an order with a negative margin"
                text += f" while calculating {symbol} market at {current_moment}"
                raise SimulationError(text)

            elif is_margin_nan:
                text = ""
                text += "Got an order with a non-numeric margin"
                text += f" while calculating {symbol} market at {current_moment}"
                raise SimulationError(text)

            # ■■■■■ mimic the real world phenomenon ■■■■■

            if would_trade_happen:
                virtual_position = chunk_virtual_state.positions[symbol]
                before_entry_price = virtual_position.entry_price
                before_amount = virtual_position.amount

                virtual_position.amount += amount_shift
                current_amount = virtual_position.amount

                # case when the position is created from 0
                if before_amount == 0 and current_amount != 0:
                    virtual_position.entry_price = fill_price
                    invested_margin = abs(current_amount) * fill_price
                    chunk_virtual_state.available_balance -= invested_margin
                # case when the position is closed from something
                elif before_amount != 0 and current_amount == 0:
                    virtual_position.entry_price = 0
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * before_amount
                    returned_margin = abs(before_amount) * before_entry_price
                    chunk_virtual_state.available_balance += returned_margin
                    chunk_virtual_state.available_balance += realized_profit
                # case when the position direction is flipped
                elif before_amount * current_amount < 0:
                    virtual_position.entry_price = fill_price
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * before_amount
                    returned_margin = abs(before_amount) * before_entry_price
                    invested_margin = abs(current_amount) * fill_price
                    chunk_virtual_state.available_balance += returned_margin
                    chunk_virtual_state.available_balance -= invested_margin
                    chunk_virtual_state.available_balance += realized_profit
                # case when the position size is increased one the same direction
                elif abs(current_amount) > abs(before_amount):
                    before_numerator = before_entry_price * before_amount
                    new_numerator = fill_price * amount_shift
                    current_numerator = before_numerator + new_numerator
                    new_entry_price = current_numerator / current_amount
                    virtual_position.entry_price = new_entry_price
                    realized_profit = 0
                    invested_margin = abs(amount_shift) * fill_price
                    chunk_virtual_state.available_balance -= invested_margin
                    chunk_virtual_state.available_balance += realized_profit
                # case when the position size is decreased one the same direction
                else:
                    virtual_position.entry_price = before_entry_price
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * (-amount_shift)
                    returned_margin = abs(amount_shift) * before_entry_price
                    chunk_virtual_state.available_balance += returned_margin
                    chunk_virtual_state.available_balance += realized_profit

                is_new_trade_found = True

                if chunk_virtual_state.available_balance < 0:
                    text = ""
                    text += "Available balance went below zero"
                    text += f" while calculating {symbol} market"
                    text += f" at {current_moment}"
                    raise SimulationError(text)

            # ■■■■■ update the account state (symbol dependent) ■■■■■

            # locations
            current_entry_price = chunk_virtual_state.positions[symbol].entry_price
            current_entry_price = current_entry_price
            current_amount = chunk_virtual_state.positions[symbol].amount
            current_margin = abs(current_amount) * current_entry_price
            current_margin = current_margin
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
                update_time=datetime.fromtimestamp(0),
            )
            chunk_account_state.positions[symbol] = symbol_position

            # placements
            symbol_placements = chunk_virtual_state.placements[symbol]
            symbol_open_orders: dict[int, OpenOrder] = {}
            for order_type, placement in symbol_placements.items():
                order_id = placement.order_id
                boundary = placement.boundary
                left_margin = placement.margin
                symbol_open_orders[order_id] = OpenOrder(
                    order_type=order_type,
                    boundary=boundary,
                    left_margin=left_margin,
                )
            chunk_account_state.open_orders[symbol] = symbol_open_orders

            # ■■■■■ record (symbol dependent) ■■■■■

            if is_new_trade_found:
                fill_time = before_moment + timedelta(milliseconds=decision_lag)
                fill_time = np.datetime64(fill_time)
                while fill_time in asset_record_ar["index"]:
                    fill_time += np.timedelta64(1, "ms")

                wallet_balance = chunk_virtual_state.available_balance
                for symbol_key, location in chunk_virtual_state.positions.items():
                    if location.amount == 0:
                        continue
                    symbol_price = candle_data_ar[cycle][f"{symbol_key}/CLOSE"]
                    if math.isnan(symbol_price):
                        continue
                    current_margin = abs(location.amount) * location.entry_price
                    wallet_balance += current_margin

                margin_ratio = abs(amount_shift) * open_price / wallet_balance

                order_id = random.randint(ORDER_ID_MIN, ORDER_ID_MAX)

                if amount_shift == 0.0:
                    raise ValueError("Amount of asset shift cannot be zero")

                if role is None:
                    raise ValueError("No trade role was specified")

                if fill_price <= 0:
                    raise ValueError("The fill price should be bigger than zero")

                original_size = asset_record_ar.shape[0]
                asset_record_ar.resize(original_size + 1)
                asset_record_ar[-1]["index"] = fill_time
                asset_record_ar[-1]["CAUSE"] = "AUTO_TRADE"
                asset_record_ar[-1]["SYMBOL"] = symbol
                asset_record_ar[-1]["SIDE"] = "BUY" if amount_shift > 0.0 else "SELL"
                asset_record_ar[-1]["FILL_PRICE"] = fill_price
                asset_record_ar[-1]["ROLE"] = role.value
                asset_record_ar[-1]["MARGIN_RATIO"] = margin_ratio
                asset_record_ar[-1]["ORDER_ID"] = order_id
                asset_record_ar[-1]["RESULT_ASSET"] = wallet_balance

                update_time = fill_time.astype(datetime).replace(tzinfo=timezone.utc)
                chunk_account_state.positions[symbol].update_time = update_time

        # ■■■■■ understand the situation ■■■■■

        wallet_balance = chunk_virtual_state.available_balance
        unrealized_profit = 0
        for symbol_key, location in chunk_virtual_state.positions.items():
            if location.amount == 0:
                continue
            symbol_price = candle_data_ar[cycle][f"{symbol_key}/CLOSE"]
            if math.isnan(symbol_price):
                continue
            current_margin = abs(location.amount) * location.entry_price
            wallet_balance += current_margin
            # assume that mark price doesn't wobble more than 5%
            key_open_price = candle_data_ar[cycle][f"{symbol_key}/OPEN"]
            key_close_price = candle_data_ar[cycle][f"{symbol_key}/CLOSE"]
            if location.amount < 0:
                basic_price = max(key_open_price, key_close_price) * 1.05
                key_high_price = candle_data_ar[cycle][f"{symbol_key}/HIGH"]
                extreme_price = min(basic_price, key_high_price)
            else:
                basic_price = min(key_open_price, key_close_price) * 0.95
                key_low_price = candle_data_ar[cycle][f"{symbol_key}/LOW"]
                extreme_price = max(basic_price, key_low_price)
            price_difference = extreme_price - location.entry_price
            unrealized_profit += price_difference * location.amount
        unrealized_change = unrealized_profit / wallet_balance

        # ■■■■■ update the account state (symbol independent) ■■■■■

        chunk_account_state.observed_until = current_moment
        chunk_account_state.wallet_balance = wallet_balance

        # ■■■■■ record (symbol independent) ■■■■■

        original_size = chunk_unrealized_changes_ar.shape[0]
        chunk_unrealized_changes_ar.resize(original_size + 1)
        chunk_unrealized_changes_ar[-1]["index"] = before_moment
        chunk_unrealized_changes_ar[-1]["0"] = unrealized_change

        # ■■■■■ make decision and place order ■■■■■

        record_row: np.record = candle_data_ar[cycle]
        current_candle_data = {
            k: float(record_row[k])
            for k in record_row.dtype.names or ()
            if k != "index"
        }
        record_row: np.record = indicators_ar[cycle]
        current_indicators = {
            k: float(record_row[k])
            for k in record_row.dtype.names or ()
            if k != "index"
        }

        decisions = decide(
            target_symbols=target_symbols,
            current_moment=current_moment,
            current_candle_data=current_candle_data,
            current_indicators=current_indicators,
            account_state=chunk_account_state.model_copy(deep=True),
            scribbles=chunk_scribbles,
            decision_script=decision_script_compiled,
        )

        for symbol_key, symbol_decisions in decisions.items():
            for order_type, decision in symbol_decisions.items():
                placement = VirtualPlacement(
                    order_id=random.randint(ORDER_ID_MIN, ORDER_ID_MAX),
                    boundary=decision.boundary,
                    margin=decision.margin,
                )
                chunk_virtual_state.placements[symbol_key][order_type] = placement

        # ■■■■■ report the progress in seconds ■■■■■

        progress_in_time: pd.Timedelta = current_moment - first_calculation_moment
        progress_in_seconds = progress_in_time.total_seconds()
        if progress_in_seconds % 3600 == 0:
            # Do NOT report the progress too often for the sake of performance
            progress_list[target_progress] = max(progress_in_seconds, 0)

    # ■■■■■ convert back numpy objects to pandas objects ■■■■■

    chunk_asset_record = pd.DataFrame(asset_record_ar)
    chunk_asset_record = chunk_asset_record.set_index("index")
    chunk_asset_record.index.name = None
    chunk_asset_record.index = pd.to_datetime(chunk_asset_record.index, utc=True)

    chunk_unrealized_changes_df = pd.DataFrame(chunk_unrealized_changes_ar)
    chunk_unrealized_changes_df = chunk_unrealized_changes_df.set_index("index")
    chunk_unrealized_changes_df.index.name = None
    chunk_unrealized_changes_df.index = pd.to_datetime(
        chunk_unrealized_changes_df.index, utc=True
    )
    chunk_unrealized_changes = chunk_unrealized_changes_df["0"]

    # ■■■■■ return calculated data ■■■■■

    calculation_output = CalculationOutput(
        chunk_asset_record=chunk_asset_record,
        chunk_unrealized_changes=chunk_unrealized_changes,
        chunk_scribbles=chunk_scribbles,
        chunk_account_state=chunk_account_state,
        chunk_virtual_state=chunk_virtual_state,
    )
    return calculation_output
