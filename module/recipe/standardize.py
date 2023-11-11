import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from module.recipe import user_settings


def candle_data():
    target_symbols = user_settings.get_data_settings()["target_symbols"]
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
    target_symbols = user_settings.get_data_settings()["target_symbols"]
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


def strategy():
    ingredients = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code_name = "".join(random.choice(ingredients) for _ in range(6))
    return {
        "code_name": code_name,
        "readable_name": "A New Blank Strategy",
        "version": "1.0",
        "description": "A blank strategy template before being written",
        "risk_level": 0,
        "parallelized_simulation": True,
        "chunk_division": 30,
        "indicators_script": "pass",
        "decision_script": "pass",
    }
