import math
from datetime import datetime, timedelta, timezone
from types import CodeType


def choose(**kwargs):
    # ■■■■■ get data ■■■■■

    target_symbols = kwargs["target_symbols"]
    current_moment = kwargs["current_moment"]
    current_candle_data = kwargs["current_candle_data"]
    current_indicators = kwargs["current_indicators"]
    account_state = kwargs["account_state"]
    scribbles = kwargs["scribbles"]
    decision_script: str | CodeType = kwargs["decision_script"]

    # ■■■■■ decision template ■■■■■

    decision = {}
    for symbol in target_symbols:
        decision[symbol] = {}

    # ■■■■■ write decisions ■■■■■

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

    exec(decision_script, namespace)

    # ■■■■■ return decision ■■■■■

    blank_symbols = []
    for symbol, symbol_decision in decision.items():
        if len(symbol_decision) == 0:
            blank_symbols.append(symbol)
    for blank_symbol in blank_symbols:
        decision.pop(blank_symbol)

    return decision, scribbles
