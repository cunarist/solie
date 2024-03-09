import math
import random
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from solie.definition.errors import SimulationError
from solie.recipe import decide


def do(dataset):
    # leverage is treated as 1
    # because those are going to be applied at the presentation phase

    # ■■■■■ get data ■■■■■

    progress_list = dataset["progress_list"]
    target_progress = dataset["target_progress"]
    target_symbols = dataset["target_symbols"]
    calculation_index: pd.DatetimeIndex = dataset["calculation_index"]
    chunk_candle_data: pd.DataFrame = dataset["chunk_candle_data"]
    chunk_indicators: pd.DataFrame = dataset["chunk_indicators"]
    chunk_asset_record: pd.DataFrame = dataset["chunk_asset_record"]
    chunk_unrealized_changes: pd.Series = dataset["chunk_unrealized_changes"]
    chunk_scribbles: dict = dataset["chunk_scribbles"]
    chunk_account_state: dict = dataset["chunk_account_state"]
    chunk_virtual_state: dict = dataset["chunk_virtual_state"]
    decision_script: str = dataset["decision_script"]

    # ■■■■■ basic values ■■■■■

    decision_lag = 3000  # milliseconds

    # ■■■■■ return blank data if there's nothing to calculate ■■■■■

    if len(calculation_index) == 0:
        dataset = {
            "chunk_asset_record": chunk_asset_record,
            "chunk_unrealized_changes": chunk_unrealized_changes,
            "chunk_scribbles": chunk_scribbles,
            "chunk_account_state": chunk_account_state,
            "chunk_virtual_state": chunk_virtual_state,
        }

        return dataset

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

            open_price = candle_data_ar[cycle][str((symbol, "Open"))]
            close_price = candle_data_ar[cycle][str((symbol, "Close"))]
            if math.isnan(open_price) or math.isnan(close_price):
                continue

            would_trade_happen = False
            is_new_trade_found = False
            amount_shift = 0
            fill_price = 0
            role = ""

            # ■■■■■ check if any order would be filled ■■■■■

            price_speed = (close_price - open_price) / 10
            is_margin_negative = False
            is_margin_nan = False

            # special placements
            if "cancel_all" in chunk_virtual_state["placements"][symbol]:
                cancel_placement_names = []
                for placement_name in chunk_virtual_state["placements"][symbol].keys():
                    if any(s in placement_name for s in ("later", "book")):
                        cancel_placement_names.append(placement_name)
                for cancel_placement_name in cancel_placement_names:
                    chunk_virtual_state["placements"][symbol].pop(cancel_placement_name)
                chunk_virtual_state["placements"][symbol].pop("cancel_all")

            # instant placements
            if "now_close" in chunk_virtual_state["placements"][symbol]:
                would_trade_happen = True
                command = chunk_virtual_state["placements"][symbol]["now_close"]
                role = "taker"
                fill_price = open_price + price_speed * (decision_lag / 1000)
                amount_shift = -chunk_virtual_state["locations"][symbol]["amount"]
                chunk_virtual_state["placements"][symbol].pop("now_close")

            if "now_buy" in chunk_virtual_state["placements"][symbol]:
                would_trade_happen = True
                command = chunk_virtual_state["placements"][symbol]["now_buy"]
                role = "taker"
                fill_price = open_price + price_speed * (decision_lag / 1000)
                fill_margin = command["margin"]
                if fill_margin < 0:
                    is_margin_negative = True
                if math.isnan(fill_margin):
                    is_margin_nan = True
                amount_shift = fill_margin / fill_price
                chunk_virtual_state["placements"][symbol].pop("now_buy")

            if "now_sell" in chunk_virtual_state["placements"][symbol]:
                would_trade_happen = True
                command = chunk_virtual_state["placements"][symbol]["now_sell"]
                role = "taker"
                fill_price = open_price + price_speed * (decision_lag / 1000)
                fill_margin = command["margin"]
                if fill_margin < 0:
                    is_margin_negative = True
                if math.isnan(fill_margin):
                    is_margin_nan = True
                amount_shift = -fill_margin / fill_price
                chunk_virtual_state["placements"][symbol].pop("now_sell")

            # conditional placements
            if "later_up_close" in chunk_virtual_state["placements"][symbol]:
                command = chunk_virtual_state["placements"][symbol]["later_up_close"]
                boundary = command["boundary"]

                wobble_high = candle_data_ar[cycle][str((symbol, "High"))]
                wobble_low = candle_data_ar[cycle][str((symbol, "Low"))]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "taker"
                    fill_price = boundary
                    amount_shift = -chunk_virtual_state["locations"][symbol]["amount"]
                    chunk_virtual_state["placements"][symbol].pop("later_up_close")

            if "later_down_close" in chunk_virtual_state["placements"][symbol]:
                command = chunk_virtual_state["placements"][symbol]["later_down_close"]
                boundary = command["boundary"]

                wobble_high = candle_data_ar[cycle][str((symbol, "High"))]
                wobble_low = candle_data_ar[cycle][str((symbol, "Low"))]
                did_cross = wobble_low < boundary < wobble_high

                if did_cross:
                    would_trade_happen = True
                    role = "taker"
                    fill_price = boundary
                    amount_shift = -chunk_virtual_state["locations"][symbol]["amount"]
                    chunk_virtual_state["placements"][symbol].pop("later_down_close")

            if "later_up_buy" in chunk_virtual_state["placements"][symbol]:
                command = chunk_virtual_state["placements"][symbol]["later_up_buy"]
                boundary = command["boundary"]

                wobble_high = candle_data_ar[cycle][str((symbol, "High"))]
                wobble_low = candle_data_ar[cycle][str((symbol, "Low"))]
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
                    chunk_virtual_state["placements"][symbol].pop("later_up_buy")

            if "later_down_buy" in chunk_virtual_state["placements"][symbol]:
                command = chunk_virtual_state["placements"][symbol]["later_down_buy"]
                boundary = command["boundary"]

                wobble_high = candle_data_ar[cycle][str((symbol, "High"))]
                wobble_low = candle_data_ar[cycle][str((symbol, "Low"))]
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
                    chunk_virtual_state["placements"][symbol].pop("later_down_buy")

            if "later_up_sell" in chunk_virtual_state["placements"][symbol]:
                command = chunk_virtual_state["placements"][symbol]["later_up_sell"]
                boundary = command["boundary"]

                wobble_high = candle_data_ar[cycle][str((symbol, "High"))]
                wobble_low = candle_data_ar[cycle][str((symbol, "Low"))]
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
                    chunk_virtual_state["placements"][symbol].pop("later_up_sell")

            if "later_down_sell" in chunk_virtual_state["placements"][symbol]:
                command = chunk_virtual_state["placements"][symbol]["later_down_sell"]
                boundary = command["boundary"]

                wobble_high = candle_data_ar[cycle][str((symbol, "High"))]
                wobble_low = candle_data_ar[cycle][str((symbol, "Low"))]
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
                    chunk_virtual_state["placements"][symbol].pop("later_down_sell")

            if "book_buy" in chunk_virtual_state["placements"][symbol]:
                command = chunk_virtual_state["placements"][symbol]["book_buy"]
                boundary = command["boundary"]

                wobble_high = candle_data_ar[cycle][str((symbol, "High"))]
                wobble_low = candle_data_ar[cycle][str((symbol, "Low"))]
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
                    chunk_virtual_state["placements"][symbol].pop("book_buy")

            if "book_sell" in chunk_virtual_state["placements"][symbol]:
                command = chunk_virtual_state["placements"][symbol]["book_sell"]
                boundary = command["boundary"]

                wobble_high = candle_data_ar[cycle][str((symbol, "High"))]
                wobble_low = candle_data_ar[cycle][str((symbol, "Low"))]
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
                    chunk_virtual_state["placements"][symbol].pop("book_sell")

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
                symbol_location = chunk_virtual_state["locations"][symbol]
                before_entry_price = symbol_location["entry_price"]
                before_amount = symbol_location["amount"]

                symbol_location["amount"] += amount_shift
                current_amount = symbol_location["amount"]

                # case when the position is created from 0
                if before_amount == 0 and current_amount != 0:
                    symbol_location["entry_price"] = fill_price
                    invested_margin = abs(current_amount) * fill_price
                    chunk_virtual_state["available_balance"] -= invested_margin
                # case when the position is closed from something
                elif before_amount != 0 and current_amount == 0:
                    symbol_location["entry_price"] = 0
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * before_amount
                    returned_margin = abs(before_amount) * before_entry_price
                    chunk_virtual_state["available_balance"] += returned_margin
                    chunk_virtual_state["available_balance"] += realized_profit
                # case when the position direction is flipped
                elif before_amount * current_amount < 0:
                    symbol_location["entry_price"] = fill_price
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * before_amount
                    returned_margin = abs(before_amount) * before_entry_price
                    invested_margin = abs(current_amount) * fill_price
                    chunk_virtual_state["available_balance"] += returned_margin
                    chunk_virtual_state["available_balance"] -= invested_margin
                    chunk_virtual_state["available_balance"] += realized_profit
                # case when the position size is increased one the same direction
                elif abs(current_amount) > abs(before_amount):
                    before_numerator = before_entry_price * before_amount
                    new_numerator = fill_price * amount_shift
                    current_numerator = before_numerator + new_numerator
                    new_entry_price = current_numerator / current_amount
                    symbol_location["entry_price"] = new_entry_price
                    realized_profit = 0
                    invested_margin = abs(amount_shift) * fill_price
                    chunk_virtual_state["available_balance"] -= invested_margin
                    chunk_virtual_state["available_balance"] += realized_profit
                # case when the position size is decreased one the same direction
                else:
                    symbol_location["entry_price"] = before_entry_price
                    price_difference = fill_price - before_entry_price
                    realized_profit = price_difference * (-amount_shift)
                    returned_margin = abs(amount_shift) * before_entry_price
                    chunk_virtual_state["available_balance"] += returned_margin
                    chunk_virtual_state["available_balance"] += realized_profit

                is_new_trade_found = True

                if chunk_virtual_state["available_balance"] < 0:
                    text = ""
                    text += "Available balance went below zero"
                    text += f" while calculating {symbol} market"
                    text += f" at {current_moment}"
                    raise SimulationError(text)

            # ■■■■■ update the account state (symbol dependent) ■■■■■

            # locations
            current_entry_price = chunk_virtual_state["locations"][symbol][
                "entry_price"
            ]
            current_entry_price = float(current_entry_price)
            current_amount = chunk_virtual_state["locations"][symbol]["amount"]
            current_margin = abs(current_amount) * current_entry_price
            current_margin = float(current_margin)
            symbol_position = {}
            symbol_position["entry_price"] = current_entry_price
            symbol_position["margin"] = current_margin
            if chunk_virtual_state["locations"][symbol]["amount"] > 0:
                symbol_position["direction"] = "long"
            if chunk_virtual_state["locations"][symbol]["amount"] < 0:
                symbol_position["direction"] = "short"
            if chunk_virtual_state["locations"][symbol]["amount"] == 0:
                symbol_position["direction"] = "none"
            chunk_account_state["positions"][symbol] = symbol_position

            # placements
            symbol_placements = chunk_virtual_state["placements"][symbol]
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
            chunk_account_state["open_orders"][symbol] = symbol_open_orders

            # ■■■■■ record (symbol dependent) ■■■■■

            if is_new_trade_found:
                fill_time = before_moment + timedelta(milliseconds=decision_lag)
                fill_time = np.datetime64(fill_time)
                while fill_time in asset_record_ar["index"]:
                    fill_time += np.timedelta64(1, "ms")

                wallet_balance = chunk_virtual_state["available_balance"]
                for symbol_key, location in chunk_virtual_state["locations"].items():
                    if location["amount"] == 0:
                        continue
                    column_key = str((symbol_key, "Close"))
                    symbol_price = candle_data_ar[cycle][column_key]
                    if math.isnan(symbol_price):
                        continue
                    current_margin = abs(location["amount"]) * location["entry_price"]
                    wallet_balance += current_margin

                margin_ratio = abs(amount_shift) * open_price / wallet_balance

                order_id = random.randint(10**18, 10**19 - 1)

                if amount_shift > 0:
                    side = "buy"
                elif amount_shift < 0:
                    side = "sell"
                else:
                    raise ValueError("Amount of asset shift cannot be 0")

                if role == "":
                    raise ValueError("No trade role was specified")

                if fill_price == 0:
                    raise ValueError("The fill price cannot be zero")

                original_size = asset_record_ar.shape[0]
                asset_record_ar.resize(original_size + 1)
                asset_record_ar[-1]["index"] = fill_time
                asset_record_ar[-1]["Cause"] = "auto_trade"
                asset_record_ar[-1]["Symbol"] = symbol
                asset_record_ar[-1]["Side"] = side
                asset_record_ar[-1]["Fill Price"] = fill_price
                asset_record_ar[-1]["Role"] = role
                asset_record_ar[-1]["Margin Ratio"] = margin_ratio
                asset_record_ar[-1]["Order ID"] = order_id
                asset_record_ar[-1]["Result Asset"] = wallet_balance

                update_time = fill_time.astype(datetime).replace(tzinfo=timezone.utc)
                chunk_account_state["positions"][symbol]["update_time"] = update_time

        # ■■■■■ understand the situation ■■■■■

        wallet_balance = chunk_virtual_state["available_balance"]
        unrealized_profit = 0
        for symbol_key, location in chunk_virtual_state["locations"].items():
            if location["amount"] == 0:
                continue
            symbol_price = candle_data_ar[cycle][str((symbol_key, "Close"))]
            if math.isnan(symbol_price):
                continue
            current_margin = abs(location["amount"]) * location["entry_price"]
            wallet_balance += current_margin
            # assume that mark price doesn't wobble more than 5%
            key_open_price = candle_data_ar[cycle][str((symbol_key, "Open"))]
            key_close_price = candle_data_ar[cycle][str((symbol_key, "Close"))]
            if location["amount"] < 0:
                basic_price = max(key_open_price, key_close_price) * 1.05
                key_high_price = candle_data_ar[cycle][str((symbol_key, "High"))]
                extreme_price = min(basic_price, key_high_price)
            else:
                basic_price = min(key_open_price, key_close_price) * 0.95
                key_low_price = candle_data_ar[cycle][str((symbol_key, "Low"))]
                extreme_price = max(basic_price, key_low_price)
            price_difference = extreme_price - location["entry_price"]
            unrealized_profit += price_difference * location["amount"]
        unrealized_change = unrealized_profit / wallet_balance

        # ■■■■■ update the account state (symbol independent) ■■■■■

        chunk_account_state["observed_until"] = current_moment
        chunk_account_state["wallet_balance"] = float(wallet_balance)

        # ■■■■■ record (symbol independent) ■■■■■

        original_size = chunk_unrealized_changes_ar.shape[0]
        chunk_unrealized_changes_ar.resize(original_size + 1)
        chunk_unrealized_changes_ar[-1]["index"] = before_moment
        chunk_unrealized_changes_ar[-1]["0"] = unrealized_change

        # ■■■■■ make decision and place order ■■■■■

        current_candle_data = candle_data_ar[cycle]
        current_indicators = indicators_ar[cycle]
        decision, chunk_scribbles = decide.choose(
            target_symbols=target_symbols,
            current_moment=current_moment,
            current_candle_data=current_candle_data,
            current_indicators=current_indicators,
            account_state=chunk_account_state.copy(),
            scribbles=chunk_scribbles,
            decision_script=decision_script_compiled,
        )

        for symbol_key, symbol_decision in decision.items():
            for each_decision in symbol_decision.values():
                each_decision["order_id"] = random.randint(10**18, 10**19 - 1)
            chunk_virtual_state["placements"][symbol_key].update(decision[symbol_key])

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

    dataset = {
        "chunk_asset_record": chunk_asset_record,
        "chunk_unrealized_changes": chunk_unrealized_changes,
        "chunk_scribbles": chunk_scribbles,
        "chunk_account_state": chunk_account_state,
        "chunk_virtual_state": chunk_virtual_state,
    }

    return dataset
