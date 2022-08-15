from datetime import datetime, timezone, timedelta
import math
import random

from module.recipe import user_settings


def choose(
    current_moment,
    current_candle_data,
    current_indicators,
    strategy,
    account_state,
    scribbles,
    compiled_custom_script,
):
    target_symbols = user_settings.get_data_settings()["target_symbols"]

    # ■■■■■ decision template ■■■■■

    decision = {}
    for symbol in target_symbols:
        decision[symbol] = {}

    # ■■■■■ write decisions ■■■■■

    if strategy == 0:
        namespace = {
            "datetime": datetime,
            "timezone": timezone,
            "timedelta": timedelta,
            "math": math,
            "target_symbols": target_symbols,
            "current_moment": current_moment,
            "current_candle_data": current_candle_data,
            "current_indicators": current_indicators,
            "account_state": account_state,
            "scribbles": scribbles,
            "decision": decision,
        }

        exec(compiled_custom_script, namespace)

    elif strategy == 1:
        for symbol in target_symbols:
            split_ratio = 0.0001

            current_price = current_candle_data[str((symbol, "Close"))]

            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            target_symbols = target_symbols
            # too little volatility on testnet markets except these symbols
            asset_token = user_settings.get_data_settings()["asset_token"]
            prefer_symbol = "BTC" + asset_token
            if prefer_symbol in target_symbols:
                should_filter = True
            else:
                should_filter = False

            if should_filter and symbol != prefer_symbol:
                continue

            if direction == "none":
                if random.random() < 0.5:
                    decision[symbol]["now_buy"] = {
                        "margin": split_ratio * wallet_balance,
                    }
                else:
                    decision[symbol]["now_sell"] = {
                        "margin": split_ratio * wallet_balance,
                    }
            else:
                decision[symbol]["now_close"] = {}
                decision[symbol]["cancel_all"] = {}

            if direction == "none":
                decision[symbol]["later_down_buy"] = {
                    "boundary": current_price * 0.92,
                    "margin": split_ratio * wallet_balance,
                }
                decision[symbol]["later_up_sell"] = {
                    "boundary": current_price * 1.08,
                    "margin": split_ratio * wallet_balance,
                }
                decision[symbol]["later_up_buy"] = {
                    "boundary": current_price * 1.1,
                    "margin": split_ratio * wallet_balance,
                }
                decision[symbol]["later_down_sell"] = {
                    "boundary": current_price * 0.9,
                    "margin": split_ratio * wallet_balance,
                }
                decision[symbol]["book_buy"] = {
                    "boundary": current_price * 0.94,
                    "margin": split_ratio * wallet_balance,
                }
                decision[symbol]["book_sell"] = {
                    "boundary": current_price * 1.06,
                    "margin": split_ratio * wallet_balance,
                }
            else:
                decision[symbol]["later_down_close"] = {
                    "boundary": current_price * 0.88,
                }
                decision[symbol]["later_up_close"] = {
                    "boundary": current_price * 1.12,
                }

    elif strategy == 2:
        for symbol in target_symbols:
            symbols_count = len(target_symbols)
            acquire_ratio = 0.8 / symbols_count / (80 * 60 / 10)  # ratio
            release_ratio = 0.8 / symbols_count / (20 * 60 / 10)  # ratio
            max_scoops = 12  # count
            next_condition = 2  # percent
            release_condition = 0.5  # percent
            max_hold_time = 80  # minutes

            current_price = current_candle_data[str((symbol, "Close"))]

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]
            entry_price = account_state["positions"][symbol]["entry_price"]

            calmness = current_indicators[
                str((symbol, "Abstract", "Calmness (#FF8888)"))
            ]
            diff_sum = current_indicators[
                str((symbol, "Abstract", "Diff Sum (#BB00FF)"))
            ]
            is_low = diff_sum < -1
            is_high = diff_sum > 4

            if direction == "none":
                scribbles[symbol + "_expected_ratio"] = 0
                scribbles[symbol + "_max_price_record"] = current_price
                scribbles[symbol + "_min_price_record"] = current_price
                scribbles[symbol + "_last_blank_time"] = current_moment

                if is_low:
                    scribbles[symbol + "_expected_ratio"] = acquire_ratio * calmness
                    decision[symbol]["now_buy"] = {
                        "margin": acquire_ratio * calmness * wallet_balance,
                    }
                if is_high:
                    scribbles[symbol + "_expected_ratio"] = acquire_ratio
                    decision[symbol]["now_sell"] = {
                        "margin": acquire_ratio * wallet_balance,
                    }

            elif direction == "long":
                safe_border = entry_price + release_condition / 100 * current_price
                is_price_safe = current_price > safe_border
                last_blank_time = scribbles[symbol + "_last_blank_time"]
                time_passed = current_moment - last_blank_time
                did_pass_long = time_passed > timedelta(minutes=max_hold_time)

                if is_price_safe:
                    scribbles[symbol + "_expected_ratio"] -= release_ratio
                    expected_ratio = scribbles[symbol + "_expected_ratio"]
                    current_ratio = margin / wallet_balance
                    ratio_shift = current_ratio - expected_ratio

                    if expected_ratio < 0:
                        decision[symbol]["now_close"] = {}

                    elif ratio_shift > 0:
                        decision[symbol]["now_sell"] = {
                            "margin": ratio_shift * wallet_balance,
                        }

                elif not is_low or did_pass_long:
                    decision[symbol]["now_close"] = {}

                else:
                    max_price_record = scribbles[symbol + "_max_price_record"]
                    min_price_record = scribbles[symbol + "_min_price_record"]
                    price_movement = min_price_record - max_price_record
                    border_distance = price_movement * (next_condition / 100)
                    next_border = max_price_record - border_distance
                    is_new_record = current_price < next_border

                    ratio_shift = acquire_ratio * calmness
                    scribbles[symbol + "_expected_ratio"] += ratio_shift
                    expected_ratio = scribbles[symbol + "_expected_ratio"]
                    current_ratio = margin / wallet_balance
                    ratio_shift = min(
                        expected_ratio - current_ratio,
                        acquire_ratio * max_scoops,
                    )

                    if ratio_shift > 0 and is_new_record:
                        scribbles[symbol + "_max_price_record"] = current_price
                        decision[symbol]["now_buy"] = {
                            "margin": ratio_shift * wallet_balance,
                        }

            elif direction == "short":
                safe_border = entry_price - release_condition / 100 * current_price
                is_price_safe = current_price < safe_border
                last_blank_time = scribbles[symbol + "_last_blank_time"]
                time_passed = current_moment - last_blank_time
                did_pass_long = time_passed > timedelta(minutes=max_hold_time)

                if is_price_safe:
                    scribbles[symbol + "_expected_ratio"] -= release_ratio
                    expected_ratio = scribbles[symbol + "_expected_ratio"]
                    current_ratio = margin / wallet_balance
                    ratio_shift = current_ratio - expected_ratio

                    if expected_ratio < 0:
                        decision[symbol]["now_close"] = {}

                    elif ratio_shift > 0:
                        decision[symbol]["now_buy"] = {
                            "margin": ratio_shift * wallet_balance,
                        }

                elif not is_high or did_pass_long:
                    decision[symbol]["now_close"] = {}

                else:
                    max_price_record = scribbles[symbol + "_max_price_record"]
                    min_price_record = scribbles[symbol + "_min_price_record"]
                    price_movement = max_price_record - min_price_record
                    border_distance = price_movement * (next_condition / 100)
                    next_border = max_price_record + border_distance
                    is_new_record = current_price > next_border

                    ratio_shift = acquire_ratio
                    scribbles[symbol + "_expected_ratio"] += ratio_shift
                    expected_ratio = scribbles[symbol + "_expected_ratio"]
                    current_ratio = margin / wallet_balance
                    ratio_shift = min(
                        expected_ratio - current_ratio,
                        acquire_ratio * max_scoops,
                    )

                    if ratio_shift > 0 and is_new_record:
                        scribbles[symbol + "_max_price_record"] = current_price
                        decision[symbol]["now_sell"] = {
                            "margin": ratio_shift * wallet_balance,
                        }

    # ■■■■■ return decision ■■■■■

    blank_symbols = []
    for symbol, symbol_decision in decision.items():
        if len(symbol_decision) == 0:
            blank_symbols.append(symbol)
    for blank_symbol in blank_symbols:
        decision.pop(blank_symbol)

    return decision, scribbles
