from datetime import datetime, timezone, timedelta
import math
import random

from module.recipe import level_constant
from module.recipe import standardize


def choose(
    current_moment,
    current_observed_data,
    current_indicators,
    strategy,
    account_state,
    scribbles,
    compiled_custom_script,
):

    target_symbols = standardize.get_basics()["target_symbols"]

    # ■■■■■ decision template ■■■■■

    decision = {}
    for symbol in target_symbols:
        decision[symbol] = {}

    # ■■■■■ write decisions ■■■■■

    if strategy == 0:

        namespace = {
            "symbol": symbol,
            "target_symbols": target_symbols,
            "current_moment": current_moment,
            "current_observed_data": current_observed_data,
            "current_indicators": current_indicators,
            "account_state": account_state,
            "scribbles": scribbles,
            "decision": decision,
        }

        exec(compiled_custom_script, namespace)

    elif strategy == 1:

        for symbol in target_symbols:

            split_ratio = 0.0001

            current_price = current_observed_data[str((symbol, "Close"))]

            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            target_symbols = target_symbols
            # too little volatility on testnet markets except these symbols
            prefer_symbols = ("BTCUSDT", "ETHUSDT")
            intersection = [
                target_symbol
                for target_symbol in target_symbols
                if symbol in prefer_symbols
            ]
            should_filter = len(intersection) > 0

            if should_filter and symbol not in prefer_symbols:
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

            split_ratio = 0.0001

            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            if symbol in ("BTCUSDT", "ETHUSDT"):
                # too little volatility on testnet markets except these symbols
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

    elif strategy == 57:

        for symbol in target_symbols:

            current_price = current_observed_data[str((symbol, "Close"))]

            interval = 1  # minutes
            wait = 12  # minutes
            margin_ratio = 0.01
            endure_time = 3  # hours
            escape_delta = 0.01
            initial_profit_delta = 0.01
            continue_time = 600  # seconds

            base_scribbles = {
                "mode": "waiting",
                "start_time": current_moment,
                "was_zero": True,
            }

            for scribble_key, scribble_value in base_scribbles.items():
                if scribble_key not in scribbles:
                    scribbles[scribble_key] = scribble_value

            current_middle = current_indicators[str((symbol, "Price", "SMA 60"))]

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            entry_price = account_state["positions"][symbol]["entry_price"]

            if direction == "none":
                scribbles["mode"] = "waiting"
                scribbles["was_zero"] = True
            elif direction == "long":
                scribbles["mode"] = "buying"
                if scribbles["was_zero"]:
                    scribbles["start_time"] = current_moment
                    scribbles["was_zero"] = False
            elif direction == "short":
                scribbles["mode"] = "selling"
                if scribbles["was_zero"]:
                    scribbles["start_time"] = current_moment
                    scribbles["was_zero"] = False

            mode = scribbles["mode"]
            start_time = scribbles["start_time"]

            is_high = current_price > current_middle
            is_low = current_price < current_middle

            needed_continue_time = timedelta(seconds=continue_time)
            important_candle_data = current_observed_data[
                current_moment - needed_continue_time :
            ]
            important_indicators = current_indicators[
                current_moment - needed_continue_time :
            ]
            did_continue_low = (
                important_indicators[str((symbol, "Price", "SMA 60 .10.10-"))]
                > important_candle_data[symbol]
            )
            did_continue_low = did_continue_low.all()
            did_continue_high = (
                important_indicators[str((symbol, "Price", "SMA 60 .10.10-"))]
                < important_candle_data[symbol]
            )
            did_continue_high = did_continue_high.all()

            time_passed = current_moment - start_time
            initial_profit = entry_price * initial_profit_delta
            needed_sigma = (timedelta(hours=endure_time) - time_passed) / timedelta(
                hours=endure_time
            )
            is_time = (
                current_moment.second == 0 and current_moment.minute % interval == 0
            )
            has_waited_enough = time_passed > timedelta(minutes=wait)
            is_wallet_balance_left = margin / wallet_balance < 1 - 2 * margin_ratio

            if mode == "waiting":

                if did_continue_low:
                    decision[symbol]["now_buy"] = {
                        "margin": margin_ratio * wallet_balance,
                    }

                elif did_continue_high:
                    decision[symbol]["now_sell"] = {
                        "margin": margin_ratio * wallet_balance,
                    }

                else:
                    decision[symbol]["later_down_buy"] = {
                        "margin": 0.01 * wallet_balance,
                        "boundary": current_price * 0.9,
                    }

                    decision[symbol]["later_up_sell"] = {
                        "margin": 0.01 * wallet_balance,
                        "boundary": current_price * 1.1,
                    }

            elif mode == "buying":

                # close position
                if has_waited_enough:
                    decision[symbol]["later_up_close"] = {
                        "boundary": entry_price + needed_sigma * initial_profit,
                    }

                else:
                    decision[symbol]["later_up_sell"] = {
                        "margin": 0.01 * wallet_balance,
                        "boundary": current_price * 1.1,
                    }

                # acquire more
                if is_time and is_low and is_wallet_balance_left:
                    decision[symbol]["now_buy"] = {
                        "margin": margin_ratio * wallet_balance,
                    }

            elif mode == "selling":

                # close position
                if has_waited_enough:
                    decision[symbol]["later_down_close"] = {
                        "boundary": entry_price - needed_sigma * initial_profit,
                    }

                else:
                    decision[symbol]["later_down_buy"] = {
                        "margin": 0.01 * wallet_balance,
                        "boundary": current_price * 0.9,
                    }

                # acquire more
                if is_time and is_high and is_wallet_balance_left:
                    decision[symbol]["now_sell"] = {
                        "margin": margin_ratio * wallet_balance,
                    }

    elif strategy == 61:

        for symbol in target_symbols:

            current_price = current_observed_data[str((symbol, "Close"))]

            interval = 10  # minutes
            wait = 15  # minutes
            margin_ratio = 0.01
            endure_time = 1  # hours
            escape_delta = 0.015
            allowed_delta = 0.04

            base_scribbles = {
                "mode": "waiting",
                "start_time": current_moment,
                "was_zero": True,
            }

            for scribble_key, scribble_value in base_scribbles.items():
                if scribble_key not in scribbles:
                    scribbles[scribble_key] = scribble_value

            current_middle = current_indicators[str((symbol, "Price", "SMA 360"))]
            i_escape_unit = current_middle * escape_delta
            i_allowed_unit = current_middle * allowed_delta

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            entry_price = account_state["positions"][symbol]["entry_price"]

            weight = max(1, abs((entry_price / current_middle) - 1) * 100 * 0.5)

            if direction == "none":
                scribbles["mode"] = "waiting"
                scribbles["was_zero"] = True
            elif direction == "long":
                scribbles["mode"] = "buying"
                if scribbles["was_zero"]:
                    scribbles["start_time"] = current_moment
                    scribbles["was_zero"] = False
            elif direction == "short":
                scribbles["mode"] = "selling"
                if scribbles["was_zero"]:
                    scribbles["start_time"] = current_moment
                    scribbles["was_zero"] = False

            mode = scribbles["mode"]
            start_time = scribbles["start_time"]

            time_passed = current_moment - start_time

            needed_sigma = max(
                (timedelta(hours=endure_time) - time_passed)
                / timedelta(hours=endure_time),
                0,
            )

            is_time = (
                current_moment.second == 0 and current_moment.minute % interval == 0
            )
            has_waited_enough = time_passed > timedelta(minutes=wait)
            is_wallet_balance_left = margin / wallet_balance < 1 - 2 * margin_ratio

            is_low = (
                current_middle - i_allowed_unit
                < current_price
                < current_middle - i_escape_unit
            )
            is_high = (
                current_middle + i_allowed_unit
                > current_price
                > current_middle + i_escape_unit
            )

            if mode == "waiting":

                if is_high:
                    decision[symbol]["now_sell"] = {
                        "margin": margin_ratio * wallet_balance,
                    }

                elif is_low:
                    decision[symbol]["now_buy"] = {
                        "margin": margin_ratio * wallet_balance,
                    }

                else:
                    decision[symbol]["later_down_buy"] = {
                        "margin": 0.01 * wallet_balance,
                        "boundary": current_price * 0.9,
                    }

                    decision[symbol]["later_up_sell"] = {
                        "margin": 0.01 * wallet_balance,
                        "boundary": current_price * 1.1,
                    }

            elif mode == "buying":

                # close position
                if not is_wallet_balance_left:
                    decision[symbol]["later_up_close"] = {
                        "boundary": current_middle + i_escape_unit,
                    }

                elif has_waited_enough and is_high:
                    decision[symbol]["now_sell"] = {
                        "margin": margin + margin_ratio * wallet_balance,
                    }

                else:
                    decision[symbol]["later_up_sell"] = {
                        "margin": 0.01 * wallet_balance,
                        "boundary": current_price * 1.1,
                    }

                # acquire more
                if is_time and is_wallet_balance_left:
                    decision[symbol]["now_buy"] = {
                        "margin": margin_ratio * wallet_balance * weight,
                    }

            elif mode == "selling":

                # close position
                if not is_wallet_balance_left:
                    decision[symbol]["later_down_close"] = {
                        "boundary": current_middle - i_escape_unit,
                    }

                elif has_waited_enough and is_low:
                    decision[symbol]["now_buy"] = {
                        "margin": margin + margin_ratio * wallet_balance,
                    }

                else:
                    decision[symbol]["later_down_buy"] = {
                        "margin": 0.01 * wallet_balance,
                        "boundary": current_price * 0.9,
                    }

                # acquire more
                if is_time and is_wallet_balance_left:
                    decision[symbol]["now_sell"] = {
                        "margin": margin_ratio * wallet_balance * weight,
                    }

    elif strategy == 64:

        for symbol in target_symbols:

            current_price = current_observed_data[str((symbol, "Close"))]

            escape_delta = 0.001
            endure_time = 3  # hours

            base_scribbles = {
                "start_time": current_moment,
                "was_zero": True,
            }

            for scribble_key, scribble_value in base_scribbles.items():
                if scribble_key not in scribbles:
                    scribbles[scribble_key] = scribble_value

            has_dived = {}
            has_leaped = {}

            current_middle = current_indicators[str((symbol, "Price", "SMA 20"))]

            start_time = scribbles["start_time"]
            was_zero = scribbles["was_zero"]

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            entry_price = account_state["positions"][symbol]["entry_price"]

            if direction == "none":
                position_level = 0
            else:
                position_level = math.floor(margin / wallet_balance * 20 + 0.2)

            is_balance_left = margin / wallet_balance < 0.9

            time_passed = current_moment - start_time
            needed_sigma = (timedelta(hours=endure_time) - time_passed) / timedelta(
                hours=endure_time
            )
            if len(current_observed_data[start_time:].index) > 1:
                standard_deviation = current_observed_data[symbol][start_time:].std()
            else:
                standard_deviation = 1000  # impossible value to occur in a short time

            for turn in range(20):

                level = turn + 1

                current_upper_limit = current_middle * (
                    1 + escape_delta * level_constant.do(level, 4 / 3)
                )
                i_lower_limit = current_middle * (
                    1 - escape_delta * level_constant.do(level, 4 / 3)
                )

                is_price_high = current_price > current_upper_limit
                is_price_low = current_price < i_lower_limit

                if is_price_low:
                    has_dived["level_" + str(level)] = True
                    has_leaped["level_" + str(level)] = False
                elif is_price_high:
                    has_dived["level_" + str(level)] = False
                    has_leaped["level_" + str(level)] = True
                else:
                    has_dived["level_" + str(level)] = False
                    has_leaped["level_" + str(level)] = False

            if direction == "none":
                scribbles["was_zero"] = True
                decision[symbol]["later_down_buy"] = {
                    "margin": wallet_balance * 0.05,
                    "boundary": current_middle * (1 - escape_delta),
                }

                decision[symbol]["later_up_sell"] = {
                    "margin": wallet_balance * 0.05,
                    "boundary": current_middle * (1 + escape_delta),
                }

            elif direction == "short":

                if was_zero:
                    scribbles["start_time"] = current_moment
                scribbles["was_zero"] = False

                next_level = position_level - 1

                if has_leaped["level_" + str(-next_level)] and is_balance_left:
                    decision[symbol]["later_up_sell"] = {
                        "margin": wallet_balance * 0.05,
                        "boundary": current_middle
                        * (1 + escape_delta * level_constant.do(-next_level, 4 / 3)),
                    }

                # close position
                decision[symbol]["later_down_close"] = {
                    "boundary": max(
                        entry_price - standard_deviation * needed_sigma, current_middle
                    ),
                }

            elif direction == "long":

                if was_zero:
                    scribbles["start_time"] = current_moment
                scribbles["was_zero"] = False

                next_level = position_level + 1

                if has_dived["level_" + str(next_level)] and is_balance_left:
                    decision[symbol]["later_down_buy"] = {
                        "margin": wallet_balance * 0.05,
                        "boundary": current_middle
                        * (1 - escape_delta * level_constant.do(next_level, 4 / 3)),
                    }

                # close position
                decision[symbol]["later_up_close"] = {
                    "boundary": min(
                        entry_price + standard_deviation * needed_sigma, current_middle
                    ),
                }

    elif strategy == 65:

        for symbol in target_symbols:

            acquire_ratio = 0.8 / len(target_symbols)

            current_price = current_observed_data[str((symbol, "Close"))]
            current_middle = current_indicators[str((symbol, "Price", "SMA 20"))]

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]
            entry_price = account_state["positions"][symbol]["entry_price"]

            if direction == "none":
                decision[symbol]["later_down_buy"] = {
                    "margin": wallet_balance * acquire_ratio,
                    "boundary": current_middle * 0.999,
                }

                decision[symbol]["later_up_sell"] = {
                    "margin": wallet_balance * acquire_ratio,
                    "boundary": current_middle * 1.001,
                }

            elif direction == "short":

                # close position
                decision[symbol]["later_down_close"] = {
                    "boundary": current_middle,
                }

            elif direction == "long":

                # close position
                decision[symbol]["later_up_close"] = {
                    "boundary": current_middle,
                }

    elif strategy == 89:

        for symbol in target_symbols:

            symbols_count = len(target_symbols)
            acquire_ratio = 0.8 / symbols_count

            current_price = current_observed_data[str((symbol, "Close"))]
            current_middle = current_indicators[str((symbol, "Price", "SMA 11520"))]

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            entry_price = account_state["positions"][symbol]["entry_price"]

            is_positive = current_price > current_middle
            is_negative = current_price < current_middle

            if direction == "none":

                if is_negative:
                    decision[symbol]["later_up_buy"] = {
                        "margin": acquire_ratio * wallet_balance,
                        "boundary": current_middle,
                    }

                elif is_positive:
                    decision[symbol]["later_down_sell"] = {
                        "margin": acquire_ratio * wallet_balance,
                        "boundary": current_middle,
                    }

            elif direction == "long":

                # close position
                decision[symbol]["later_down_close"] = {
                    "boundary": current_middle,
                }

            elif direction == "short":

                # close position
                decision[symbol]["later_down_close"] = {
                    "boundary": current_middle,
                }

    elif strategy == 93:

        for symbol in target_symbols:

            current_price = current_observed_data[str((symbol, "Close"))]

            base_scribbles = {"last_zero_time": current_moment}

            for scribble_key, scribble_value in base_scribbles.items():
                if scribble_key not in scribbles:
                    scribbles[scribble_key] = scribble_value

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            entry_price = account_state["positions"][symbol]["entry_price"]

            dimensions = [1, 4, 16, 64]
            is_rising = True
            is_falling = True

            for dimension in dimensions:
                name = str(dimension)
                delta = (
                    current_indicators[str((symbol, "Price", f"SMA {name}"))]
                    - current_observed_data[-2][str((symbol, "Price", f"SMA {name}"))]
                )
                percent = delta / current_price * 100
                speed = percent * (3600 / 10)
                needed = 5 / math.sqrt(dimension)
                if speed > -needed:
                    is_falling = False
                elif speed < needed:
                    is_rising = False

            if direction == "none":
                if is_rising:
                    decision[symbol]["now_buy"] = {
                        "margin": 0.15 * wallet_balance,
                    }

                elif is_falling:
                    decision[symbol]["now_sell"] = {
                        "margin": 0.15 * wallet_balance,
                    }

            elif direction == "long":
                if is_falling:
                    decision[symbol]["now_sell"] = {
                        "margin": margin + 0.15 * wallet_balance,
                    }

            elif direction == "short":
                if is_rising:
                    decision[symbol]["now_buy"] = {
                        "margin": margin + 0.15 * wallet_balance,
                    }

    elif strategy == 95:

        for symbol in target_symbols:

            interval = 5  # minutes
            hold_duration = 1440  # minutes
            margin_ratio = 0.01

            current_price = current_observed_data[str((symbol, "Close"))]
            current_middle = current_indicators[str((symbol, "Price", "BBANDS 120"))]

            wallet_balance = account_state["wallet_balance"]
            positions = account_state["positions"].values()
            position_balance = sum([p["margin"] for p in positions])
            direction = account_state["positions"][symbol]["direction"]
            entry_price = account_state["positions"][symbol]["entry_price"]
            margin = account_state["positions"][symbol]["margin"]

            default_value = datetime.fromtimestamp(0, tz=timezone.utc)
            last_blank_time = scribbles.get("last_blank_time", default_value)
            time_passed = current_moment - last_blank_time

            is_balance_left = position_balance / wallet_balance < 0.8

            is_positive = current_price > current_middle
            is_negative = current_price < current_middle

            loss_ratio = max(0, 1 - (time_passed / timedelta(minutes=30)))
            allowed_loss = current_price * 0.002 * loss_ratio

            if direction == "none":

                scribbles["last_blank_time"] = current_moment

                if is_positive:
                    decision[symbol]["now_buy"] = {
                        "margin": margin_ratio * wallet_balance,
                    }

                elif is_negative:
                    decision[symbol]["now_sell"] = {
                        "margin": margin_ratio * wallet_balance,
                    }

            elif direction == "long":

                did_fall = current_price < entry_price - allowed_loss
                time_ratio = time_passed / timedelta(minutes=interval)
                needed_margin = time_ratio * margin_ratio * wallet_balance * 1
                should_pay_more = needed_margin > margin + wallet_balance * margin_ratio
                did_hold_long = time_passed > timedelta(minutes=hold_duration)

                if did_fall:
                    decision[symbol]["now_close"] = {}

                elif did_hold_long:
                    decision[symbol]["now_close"] = {}

                elif should_pay_more and is_balance_left:
                    decision[symbol]["now_buy"] = {
                        "margin": needed_margin - margin,
                    }

            elif direction == "short":

                did_rise = current_price > entry_price + allowed_loss
                time_ratio = time_passed / timedelta(minutes=interval)
                needed_margin = time_ratio * margin_ratio * wallet_balance * (-1)
                should_pay_more = needed_margin > margin + wallet_balance * margin_ratio
                did_hold_long = time_passed > timedelta(minutes=hold_duration)

                if did_rise:
                    decision[symbol]["now_close"] = {}

                elif did_hold_long:
                    decision[symbol]["now_close"] = {}

                elif should_pay_more and is_balance_left:
                    decision[symbol]["now_sell"] = {
                        "margin": needed_margin - margin,
                    }

    elif strategy == 98:

        for symbol in target_symbols:

            current_price = current_observed_data[str((symbol, "Close"))]

            current_sma = current_indicators[str((symbol, "Price", "SMA 11520"))]
            before_sma = current_indicators[-2][str((symbol, "Price", "SMA 11520"))]
            sma_delta = current_sma - before_sma
            i_speed = (sma_delta / current_price * 100) / (10 / (3600 * 24))
            # percent per day

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]
            if direction == "short":
                sided_margin = -margin
            else:
                sided_margin = margin

            entry_price = account_state["positions"][symbol]["entry_price"]
            update_time = account_state["positions"][symbol]["update_time"]

            should_update = current_moment - update_time > timedelta(hours=6)

            if should_update and not math.isnan(i_speed):
                expected_sided_ratio = -i_speed / 50
                expected_sided_ratio = min(0.15, expected_sided_ratio)
                expected_sided_ratio = max(-0.15, expected_sided_ratio)
                # 2% of wallet balance when speed is 1%/day

                expected_sided_margin = expected_sided_ratio * wallet_balance

                shift = expected_sided_margin - sided_margin

                if shift < 0:
                    decision[symbol]["now_sell"] = {
                        "margin": abs(shift),
                    }

                elif shift > 0:
                    decision[symbol]["now_buy"] = {
                        "margin": abs(shift),
                    }

    elif strategy == 100:

        for symbol in target_symbols:

            current_price = current_observed_data[str((symbol, "Close"))]

            base_loss = 1  # percent

            base_scribbles = {}

            for scribble_key, scribble_value in base_scribbles.items():
                if scribble_key not in scribbles:
                    scribbles[scribble_key] = scribble_value

            margin = account_state["positions"][symbol]["margin"]
            wallet_balance = account_state["wallet_balance"]
            direction = account_state["positions"][symbol]["direction"]

            entry_price = account_state["positions"][symbol]["entry_price"]
            update_time = account_state["positions"][symbol]["update_time"]

            dimensions = [1, 4, 16, 64]
            power = 0

            for dimension in dimensions:
                name = str(dimension)
                distance = (
                    (
                        current_price
                        - current_indicators[str((symbol, "Price", f"SMA {name}"))]
                    )
                    / current_price
                    * 100
                )
                power += distance

            if direction == "none":
                if power > 2:
                    decision[symbol]["now_buy"] = {
                        "margin": 0.15 * wallet_balance,
                    }

                elif power < -2:
                    decision[symbol]["now_sell"] = {
                        "margin": 0.15 * wallet_balance,
                    }

            elif direction == "long":
                decision[symbol]["later_down_close"] = {
                    "boundary": entry_price * (1 - base_loss / 100),
                }

                if power < 0:
                    decision[symbol]["now_close"] = {}

            elif direction == "short":
                decision[symbol]["later_up_close"] = {
                    "boundary": entry_price * (1 + base_loss / 100),
                }

                if power > 0:
                    decision[symbol]["now_close"] = {}

    elif strategy == 107:

        for symbol in target_symbols:

            acquire_ratio = 0.8
            hold_duration = 1  # minutes
            wait_duration = 10  # minutes

            wallet_balance = account_state["wallet_balance"]
            positions = account_state["positions"].values()
            position_balance = sum([p["margin"] for p in positions])
            available_balance = wallet_balance - position_balance
            direction = account_state["positions"][symbol]["direction"]
            margin = account_state["positions"][symbol]["margin"]

            if direction == "none":

                volume_current = current_observed_data[str((symbol, "Volume"))]
                volume_sma = current_indicators[
                    str((symbol, "Volume", "SMA (#666666)"))
                ]

                is_wild = volume_current > volume_sma
                safe_ratio = 1 - (1 - acquire_ratio) * 0.5
                can_acquire = available_balance / wallet_balance > safe_ratio

                passed_time = (
                    current_moment - account_state["positions"][symbol]["update_time"]
                )
                did_pass_enough = passed_time > timedelta(minutes=wait_duration)

                open_price = current_observed_data[str((symbol, "Open"))]
                close_price = current_observed_data[str((symbol, "Close"))]

                did_rise = open_price < close_price
                did_fall = open_price > close_price

                scribbles[symbol + "_last_blank_time"] = current_moment

                is_decision_blank = True
                for symbol_decision in decision.values():
                    if len(symbol_decision) != 0:
                        is_decision_blank = False

                if is_wild and can_acquire and did_pass_enough and is_decision_blank:
                    if did_rise:
                        decision[symbol]["now_sell"] = {
                            "margin": wallet_balance * acquire_ratio
                        }
                    elif did_fall:
                        decision[symbol]["now_buy"] = {
                            "margin": wallet_balance * acquire_ratio
                        }

            else:

                hold_time = current_moment - scribbles[symbol + "_last_blank_time"]
                expected_ratio = (
                    1 - hold_time / timedelta(minutes=hold_duration)
                ) * acquire_ratio
                current_ratio = margin / wallet_balance
                ratio_shift = current_ratio - expected_ratio

                if expected_ratio <= 0:
                    decision[symbol]["now_close"] = {}
                else:
                    if direction == "long":
                        decision[symbol]["now_sell"] = {
                            "margin": wallet_balance * ratio_shift
                        }
                    elif direction == "short":
                        decision[symbol]["now_buy"] = {
                            "margin": wallet_balance * ratio_shift
                        }

    elif strategy == 110:

        for symbol in target_symbols:

            symbols_count = len(target_symbols)
            acquire_ratio = 0.8 / symbols_count / (80 * 60 / 10)  # ratio
            release_ratio = 0.8 / symbols_count / (20 * 60 / 10)  # ratio
            max_scoops = 12  # count
            next_condition = 2  # percent
            release_condition = 0.5  # percent
            max_hold_time = 80  # minutes

            current_price = current_observed_data[str((symbol, "Close"))]

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

    return decision
