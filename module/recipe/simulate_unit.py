import math
import random
from datetime import datetime, timezone, timedelta
import copy

import numpy as np
import pandas as pd

from module.instrument.simluation_error import SimulationError
from module.recipe import decide
from module.recipe import standardize


def do(dataset):

    # leverage is treated as 1
    # fee is treated as 0
    # because those are going to be applied at the presentation phase

    # ■■■■■ get data ■■■■■

    progress_list = dataset["progress_list"]
    target_progress = dataset["target_progress"]
    strategy = dataset["strategy"]
    is_fast_strategy = dataset["is_fast_strategy"]
    unit_observed_data = dataset["unit_observed_data"]
    unit_indicators = dataset["unit_indicators"]
    unit_trade_record = dataset["unit_trade_record"]
    unit_asset_trace = dataset["unit_asset_trace"]
    unit_unrealized_changes = dataset["unit_unrealized_changes"]
    unit_scribbles = dataset["unit_scribbles"]
    unit_account_state = dataset["unit_account_state"]
    unit_behind_state = dataset["unit_behind_state"]
    calculate_from = dataset["calculate_from"]
    calculate_until = dataset["calculate_until"]
    decision_script = dataset["decision_script"]

    # ■■■■■ basic values ■■■■■

    decision_lag = 60 if is_fast_strategy else 3000  # milliseconds
    target_moments = unit_observed_data[calculate_from:calculate_until].index

    # ■■■■■ return blank data if there's nothing to calculate ■■■■■

    if len(target_moments) == 0:

        dataset = {
            "unit_trade_record": unit_trade_record,
            "unit_asset_trace": unit_asset_trace,
            "unit_unrealized_changes": unit_unrealized_changes,
            "unit_scribbles": unit_scribbles,
            "unit_account_state": unit_account_state,
            "unit_behind_state": unit_behind_state,
        }

        return dataset

    # ■■■■■ convert to numpy objects for fast calculation ■■■■■

    target_moments_ar = target_moments.to_numpy()  # inside are datetime objects

    sliced_observed_data = unit_observed_data[calculate_from:calculate_until]
    observed_data_ar = sliced_observed_data.to_records()

    sliced_indicators = unit_indicators[calculate_from:calculate_until]
    indicators_ar = sliced_indicators.to_records()

    trade_record_ar = unit_trade_record.to_records()
    asset_trace_ar = unit_asset_trace.to_frame().to_records()
    unit_unrealized_changes_ar = unit_unrealized_changes.to_frame().to_records()

    # ■■■■■ actual loop calculation ■■■■■

    target_moments_length = len(target_moments_ar)
    compiled_decision_script = compile(decision_script, "<string>", "exec")
    target_symbols = standardize.get_basics()["target_symbols"]

    for cycle in range(target_moments_length):

        before_moment = target_moments_ar[cycle]
        if is_fast_strategy:
            current_moment = before_moment + timedelta(milliseconds=100)
        else:
            current_moment = before_moment + timedelta(seconds=10)

        for symbol in target_symbols:

            # ■■■■■ basic variables ■■■■■

            if is_fast_strategy:
                column_key = str((symbol, "Best Bid Price"))
                best_bid_price = observed_data_ar[cycle][column_key]
                column_key = str((symbol, "Best Ask Price"))
                best_ask_price = observed_data_ar[cycle][column_key]
                middle_price = (best_ask_price + best_bid_price) / 2
                if math.isnan(best_bid_price) or math.isnan(best_ask_price):
                    continue
            else:
                open_price = observed_data_ar[cycle][str((symbol, "Open"))]
                close_price = observed_data_ar[cycle][str((symbol, "Close"))]
                if math.isnan(open_price) or math.isnan(close_price):
                    continue

            would_trade_happen = False
            did_found_new_trade = False

            # ■■■■■ check if any order would be filled ■■■■■

            if not is_fast_strategy:
                price_speed = (close_price - open_price) / 10
            is_margin_negative = False
            is_margin_nan = False

            # special placements
            if "cancel_all" in unit_behind_state["placements"][symbol]:
                cancel_placement_names = []
                for placement_name in unit_behind_state["placements"][symbol].keys():
                    if any(s in placement_name for s in ("later", "book")):
                        cancel_placement_names.append(placement_name)
                for cancel_placement_name in cancel_placement_names:
                    unit_behind_state["placements"][symbol].pop(cancel_placement_name)
                unit_behind_state["placements"][symbol].pop("cancel_all")

            # instant placements
            if "now_close" in unit_behind_state["placements"][symbol]:
                would_trade_happen = True
                command = unit_behind_state["placements"][symbol]["now_close"]
                role = "taker"
                if is_fast_strategy:
                    fill_price = middle_price
                else:
                    fill_price = open_price + price_speed * (decision_lag / 1000)
                amount_shift = -unit_behind_state["locations"][symbol]["amount"]
                unit_behind_state["placements"][symbol].pop("now_close")

            if "now_buy" in unit_behind_state["placements"][symbol]:
                would_trade_happen = True
                command = unit_behind_state["placements"][symbol]["now_buy"]
                role = "taker"
                if is_fast_strategy:
                    fill_price = best_bid_price
                else:
                    fill_price = open_price + price_speed * (decision_lag / 1000)
                fill_margin = command["margin"]
                if fill_margin < 0:
                    is_margin_negative = True
                if math.isnan(fill_margin):
                    is_margin_nan = True
                amount_shift = fill_margin / fill_price
                unit_behind_state["placements"][symbol].pop("now_buy")

            if "now_sell" in unit_behind_state["placements"][symbol]:
                would_trade_happen = True
                command = unit_behind_state["placements"][symbol]["now_sell"]
                role = "taker"
                if is_fast_strategy:
                    fill_price = best_ask_price
                else:
                    fill_price = open_price + price_speed * (decision_lag / 1000)
                fill_margin = command["margin"]
                if fill_margin < 0:
                    is_margin_negative = True
                if math.isnan(fill_margin):
                    is_margin_nan = True
                amount_shift = -fill_margin / fill_price
                unit_behind_state["placements"][symbol].pop("now_sell")

            # conditional placements
            if "later_up_close" in unit_behind_state["placements"][symbol]:

                command = unit_behind_state["placements"][symbol]["later_up_close"]
                boundary = command["boundary"]

                if is_fast_strategy:
                    did_cross = boundary < middle_price
                else:
                    wobble_high = observed_data_ar[cycle][str((symbol, "High"))]
                    wobble_low = observed_data_ar[cycle][str((symbol, "Low"))]
                    did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "taker"
                    fill_price = boundary
                    amount_shift = -unit_behind_state["locations"][symbol]["amount"]
                    unit_behind_state["placements"][symbol].pop("later_up_close")

            if "later_down_close" in unit_behind_state["placements"][symbol]:

                command = unit_behind_state["placements"][symbol]["later_down_close"]
                boundary = command["boundary"]

                if is_fast_strategy:
                    did_cross = boundary > middle_price
                else:
                    wobble_high = observed_data_ar[cycle][str((symbol, "High"))]
                    wobble_low = observed_data_ar[cycle][str((symbol, "Low"))]
                    did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "taker"
                    fill_price = boundary
                    amount_shift = -unit_behind_state["locations"][symbol]["amount"]
                    unit_behind_state["placements"][symbol].pop("later_down_close")

            if "later_up_buy" in unit_behind_state["placements"][symbol]:

                command = unit_behind_state["placements"][symbol]["later_up_buy"]
                boundary = command["boundary"]

                if is_fast_strategy:
                    did_cross = boundary < middle_price
                else:
                    wobble_high = observed_data_ar[cycle][str((symbol, "High"))]
                    wobble_low = observed_data_ar[cycle][str((symbol, "Low"))]
                    did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "taker"
                    fill_price = boundary
                    fill_margin = command["margin"]
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = fill_margin / fill_price
                    unit_behind_state["placements"][symbol].pop("later_up_buy")

            if "later_down_buy" in unit_behind_state["placements"][symbol]:

                command = unit_behind_state["placements"][symbol]["later_down_buy"]
                boundary = command["boundary"]

                if is_fast_strategy:
                    did_cross = boundary > middle_price
                else:
                    wobble_high = observed_data_ar[cycle][str((symbol, "High"))]
                    wobble_low = observed_data_ar[cycle][str((symbol, "Low"))]
                    did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "taker"
                    fill_price = boundary
                    fill_margin = command["margin"]
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = fill_margin / fill_price
                    unit_behind_state["placements"][symbol].pop("later_down_buy")

            if "later_up_sell" in unit_behind_state["placements"][symbol]:

                command = unit_behind_state["placements"][symbol]["later_up_sell"]
                boundary = command["boundary"]

                if is_fast_strategy:
                    did_cross = boundary < middle_price
                else:
                    wobble_high = observed_data_ar[cycle][str((symbol, "High"))]
                    wobble_low = observed_data_ar[cycle][str((symbol, "Low"))]
                    did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "taker"
                    fill_price = boundary
                    fill_margin = command["margin"]
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = -fill_margin / fill_price
                    unit_behind_state["placements"][symbol].pop("later_up_sell")

            if "later_down_sell" in unit_behind_state["placements"][symbol]:

                command = unit_behind_state["placements"][symbol]["later_down_sell"]
                boundary = command["boundary"]

                if is_fast_strategy:
                    did_cross = boundary > middle_price
                else:
                    wobble_high = observed_data_ar[cycle][str((symbol, "High"))]
                    wobble_low = observed_data_ar[cycle][str((symbol, "Low"))]
                    did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "taker"
                    fill_price = boundary
                    fill_margin = command["margin"]
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = -fill_margin / fill_price
                    unit_behind_state["placements"][symbol].pop("later_down_sell")

            if "book_buy" in unit_behind_state["placements"][symbol]:

                command = unit_behind_state["placements"][symbol]["book_buy"]
                boundary = command["boundary"]

                if is_fast_strategy:
                    did_cross = boundary > middle_price
                else:
                    wobble_high = observed_data_ar[cycle][str((symbol, "High"))]
                    wobble_low = observed_data_ar[cycle][str((symbol, "Low"))]
                    did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "maker"
                    fill_price = boundary
                    fill_margin = command["margin"]
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = fill_margin / fill_price
                    unit_behind_state["placements"][symbol].pop("book_buy")

            if "book_sell" in unit_behind_state["placements"][symbol]:

                command = unit_behind_state["placements"][symbol]["book_sell"]
                boundary = command["boundary"]

                if is_fast_strategy:
                    did_cross = boundary < middle_price
                else:
                    wobble_high = observed_data_ar[cycle][str((symbol, "High"))]
                    wobble_low = observed_data_ar[cycle][str((symbol, "Low"))]
                    did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "maker"
                    fill_price = boundary
                    fill_margin = command["margin"]
                    if fill_margin < 0:
                        is_margin_negative = True
                    if math.isnan(fill_margin):
                        is_margin_nan = True
                    amount_shift = -fill_margin / fill_price
                    unit_behind_state["placements"][symbol].pop("book_sell")

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

                symbol_location = unit_behind_state["locations"][symbol]
                before_entry_price = symbol_location["entry_price"]
                before_amount = symbol_location["amount"]

                symbol_location["amount"] += amount_shift
                current_amount = symbol_location["amount"]

                # case when the position is created from 0
                if before_amount == 0 and current_amount != 0:
                    symbol_location["entry_price"] = fill_price
                    invested_margin = abs(current_amount) * fill_price
                    unit_behind_state["available_balance"] -= invested_margin
                # case when the position is closed from something
                elif before_amount != 0 and current_amount == 0:
                    symbol_location["entry_price"] = 0
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * before_amount
                    returned_margin = abs(before_amount) * before_entry_price
                    unit_behind_state["available_balance"] += returned_margin
                    unit_behind_state["available_balance"] += realized_profit
                # case when the position direction is flipped
                elif before_amount * current_amount < 0:
                    symbol_location["entry_price"] = fill_price
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * before_amount
                    returned_margin = abs(before_amount) * before_entry_price
                    invested_margin = abs(current_amount) * fill_price
                    unit_behind_state["available_balance"] += returned_margin
                    unit_behind_state["available_balance"] -= invested_margin
                    unit_behind_state["available_balance"] += realized_profit
                # case when the position size is increased one the same direction
                elif abs(current_amount) > abs(before_amount):
                    before_numerator = before_entry_price * before_amount
                    new_numerator = fill_price * amount_shift
                    current_numerator = before_numerator + new_numerator
                    new_entry_price = current_numerator / current_amount
                    symbol_location["entry_price"] = new_entry_price
                    realized_profit = 0
                    invested_margin = abs(amount_shift) * fill_price
                    unit_behind_state["available_balance"] -= invested_margin
                    unit_behind_state["available_balance"] += realized_profit
                # case when the position size is decreased one the same direction
                else:
                    symbol_location["entry_price"] = before_entry_price
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * (-amount_shift)
                    returned_margin = abs(amount_shift) * before_entry_price
                    unit_behind_state["available_balance"] += returned_margin
                    unit_behind_state["available_balance"] += realized_profit

                did_found_new_trade = True

                if unit_behind_state["available_balance"] < 0:
                    text = ""
                    text += "Available balance went below zero"
                    text += f" while calculating {symbol} market"
                    text += f" at {current_moment}"
                    raise SimulationError(text)

            # ■■■■■ update the account state (symbol dependent) ■■■■■

            # locations
            current_entry_price = unit_behind_state["locations"][symbol]["entry_price"]
            current_entry_price = float(current_entry_price)
            current_amount = unit_behind_state["locations"][symbol]["amount"]
            current_margin = abs(current_amount) * current_entry_price
            current_margin = float(current_margin)
            unit_account_state["positions"][symbol]["entry_price"] = current_entry_price
            unit_account_state["positions"][symbol]["margin"] = current_margin
            if unit_behind_state["locations"][symbol]["amount"] > 0:
                unit_account_state["positions"][symbol]["direction"] = "long"
            if unit_behind_state["locations"][symbol]["amount"] < 0:
                unit_account_state["positions"][symbol]["direction"] = "short"
            if unit_behind_state["locations"][symbol]["amount"] == 0:
                unit_account_state["positions"][symbol]["direction"] = "none"

            # placements
            symbol_placements = unit_behind_state["placements"][symbol]
            symbol_open_orders = {}
            for command_name, placement in symbol_placements.items():
                order_id = placement["order_id"]
                boundary = float(placement["boundary"])
                if "margin" in placement.keys():
                    left_margin = float(placement["margin"])
                else:
                    left_margin = None
                symbol_open_orders[order_id] = {
                    "command_name": command_name,
                    "boundary": boundary,
                    "left_margin": left_margin,
                }
            unit_account_state["open_orders"][symbol] = symbol_open_orders

            # ■■■■■ record (symbol dependent) ■■■■■

            if did_found_new_trade:

                fill_time = before_moment + timedelta(milliseconds=decision_lag)
                fill_time = np.datetime64(fill_time)
                while fill_time in trade_record_ar["index"]:
                    fill_time += np.timedelta64(1, "ms")

                wallet_balance = unit_behind_state["available_balance"]
                for symbol_key, location in unit_behind_state["locations"].items():
                    if location["amount"] == 0:
                        continue
                    if is_fast_strategy:
                        column_key = str((symbol_key, "Best Bid Price"))
                        best_bid_price = observed_data_ar[cycle][column_key]
                        column_key = str((symbol_key, "Best Ask Price"))
                        best_ask_price = observed_data_ar[cycle][column_key]
                        symbol_price = (best_ask_price + best_bid_price) / 2
                    else:
                        column_key = str((symbol_key, "Close"))
                        symbol_price = observed_data_ar[cycle][column_key]
                    if math.isnan(symbol_price):
                        continue
                    current_margin = abs(location["amount"]) * location["entry_price"]
                    wallet_balance += current_margin

                original_size = asset_trace_ar.shape[0]
                asset_trace_ar.resize(original_size + 1)
                asset_trace_ar[-1]["index"] = fill_time
                asset_trace_ar[-1]["0"] = wallet_balance

                if amount_shift > 0:
                    side = "buy"
                elif amount_shift < 0:
                    side = "sell"

                if is_fast_strategy:
                    margin_ratio = abs(amount_shift) * middle_price / wallet_balance
                else:
                    margin_ratio = abs(amount_shift) * open_price / wallet_balance

                order_id = random.randint(10**18, 10**19 - 1)

                original_size = trade_record_ar.shape[0]
                trade_record_ar.resize(original_size + 1)
                trade_record_ar[-1]["index"] = fill_time
                trade_record_ar[-1]["Side"] = side
                trade_record_ar[-1]["Symbol"] = symbol
                trade_record_ar[-1]["Fill Price"] = fill_price
                trade_record_ar[-1]["Role"] = role
                trade_record_ar[-1]["Margin Ratio"] = margin_ratio
                trade_record_ar[-1]["Order ID"] = order_id

                update_time = fill_time.astype(datetime).replace(tzinfo=timezone.utc)
                unit_account_state["positions"][symbol]["update_time"] = update_time

        # ■■■■■ understand the situation ■■■■■

        wallet_balance = unit_behind_state["available_balance"]
        unrealized_profit = 0
        for symbol_key, location in unit_behind_state["locations"].items():
            if location["amount"] == 0:
                continue
            if is_fast_strategy:
                column_key = str((symbol_key, "Best Bid Price"))
                best_bid_price = observed_data_ar[cycle][column_key]
                column_key = str((symbol_key, "Best Ask Price"))
                best_ask_price = observed_data_ar[cycle][column_key]
                symbol_price = (best_ask_price + best_bid_price) / 2
            else:
                symbol_price = observed_data_ar[cycle][str((symbol_key, "Close"))]
            if math.isnan(symbol_price):
                continue
            current_margin = abs(location["amount"]) * location["entry_price"]
            wallet_balance += current_margin
            if is_fast_strategy:
                column_key = str((symbol_key, "Best Bid Price"))
                best_bid_price = observed_data_ar[cycle][column_key]
                column_key = str((symbol_key, "Best Ask Price"))
                best_ask_price = observed_data_ar[cycle][column_key]
                extreme_price = (best_ask_price + best_bid_price) / 2
            else:
                # assume that mark price doesn't wobble more than 5%
                key_open_price = observed_data_ar[cycle][str((symbol_key, "Open"))]
                key_close_price = observed_data_ar[cycle][str((symbol_key, "Close"))]
                if location["amount"] < 0:
                    basic_price = max(key_open_price, key_close_price) * 1.05
                    key_high_price = observed_data_ar[cycle][str((symbol_key, "High"))]
                    extreme_price = min(basic_price, key_high_price)
                else:
                    basic_price = min(key_open_price, key_close_price) * 0.95
                    key_low_price = observed_data_ar[cycle][str((symbol_key, "Low"))]
                    extreme_price = max(basic_price, key_low_price)
            price_difference = extreme_price - location["entry_price"]
            unrealized_profit += price_difference * location["amount"]
        unrealized_change = unrealized_profit / wallet_balance

        # ■■■■■ update the account state (symbol independent) ■■■■■

        unit_account_state["observed_until"] = current_moment
        unit_account_state["wallet_balance"] = float(wallet_balance)

        # ■■■■■ record (symbol independent) ■■■■■

        original_size = unit_unrealized_changes_ar.shape[0]
        unit_unrealized_changes_ar.resize(original_size + 1)
        unit_unrealized_changes_ar[-1]["index"] = before_moment
        unit_unrealized_changes_ar[-1]["0"] = unrealized_change

        # ■■■■■ make decision and place order ■■■■■

        current_observed_data = observed_data_ar[cycle]
        current_indicators = indicators_ar[cycle]
        decision = decide.choose(
            current_moment=current_moment,
            current_observed_data=current_observed_data,
            current_indicators=current_indicators,
            strategy=strategy,
            account_state=copy.deepcopy(unit_account_state),
            scribbles=unit_scribbles,
            compiled_custom_script=compiled_decision_script,
        )

        for symbol_key, symbol_decision in decision.items():
            for each_decision in symbol_decision.values():
                each_decision["order_id"] = random.randint(10**18, 10**19 - 1)
            unit_behind_state["placements"][symbol_key].update(decision[symbol_key])

        # ■■■■■ report the progress in seconds ■■■■■

        progress_list[target_progress] = max(
            (current_moment - target_moments[0]).total_seconds(), 0
        )

    # ■■■■■ convert back numpy objects to pandas objects ■■■■■

    unit_trade_record = pd.DataFrame(trade_record_ar)
    unit_trade_record = unit_trade_record.set_index("index")
    unit_trade_record.index.name = None
    unit_trade_record.index = pd.to_datetime(unit_trade_record.index, utc=True)

    unit_asset_trace = pd.DataFrame(asset_trace_ar)
    unit_asset_trace = unit_asset_trace.set_index("index")
    unit_asset_trace.index.name = None
    unit_asset_trace.index = pd.to_datetime(unit_asset_trace.index, utc=True)
    unit_asset_trace = unit_asset_trace["0"]

    unit_unrealized_changes = pd.DataFrame(unit_unrealized_changes_ar)
    unit_unrealized_changes = unit_unrealized_changes.set_index("index")
    unit_unrealized_changes.index.name = None
    unit_unrealized_changes.index = pd.to_datetime(
        unit_unrealized_changes.index, utc=True
    )
    unit_unrealized_changes = unit_unrealized_changes["0"]

    if is_fast_strategy:
        unit_unrealized_changes = unit_unrealized_changes.resample("10s").ffill()

    # ■■■■■ return calculated data ■■■■■

    dataset = {
        "unit_trade_record": unit_trade_record,
        "unit_asset_trace": unit_asset_trace,
        "unit_unrealized_changes": unit_unrealized_changes,
        "unit_scribbles": unit_scribbles,
        "unit_account_state": unit_account_state,
        "unit_behind_state": unit_behind_state,
    }

    return dataset
