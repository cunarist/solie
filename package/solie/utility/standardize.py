import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import solie


def candle_data():
    target_symbols = solie.window.data_settings.target_symbols
    return pd.DataFrame(
        columns=pd.MultiIndex.from_product(
            [
                target_symbols,
                ("Open", "High", "Low", "Close", "Volume"),
            ]
        ),
        dtype=np.float32,
        index=pd.DatetimeIndex([], tz="UTC"),
    )


def account_state():
    target_symbols = solie.window.data_settings.target_symbols
    return {
        "observed_until": datetime.fromtimestamp(0, tz=timezone.utc),
        "wallet_balance": 1,
        "positions": {
            symbol: {
                "margin": 0,
                "direction": "none",
                "entry_price": 0,
                "update_time": datetime.fromtimestamp(0, tz=timezone.utc),
            }
            for symbol in target_symbols
        },
        "open_orders": {symbol: {} for symbol in target_symbols},
    }


def asset_record():
    return pd.DataFrame(
        columns=[
            "Cause",
            "Symbol",
            "Side",
            "Fill Price",
            "Role",
            "Margin Ratio",
            "Order ID",
            "Result Asset",
        ],
        index=pd.DatetimeIndex([], tz="UTC"),
    )


def unrealized_changes():
    return pd.Series(index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32)


def create_strategy_code_name() -> str:
    ingredients = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code_name = "".join(random.choice(ingredients) for _ in range(6))
    return code_name
