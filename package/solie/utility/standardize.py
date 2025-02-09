import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .structs import AccountState, Position, PositionDirection


def create_empty_candle_data(target_symbols: list[str]):
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


def create_empty_account_state(target_symbols: list[str]) -> AccountState:
    return AccountState(
        observed_until=datetime.fromtimestamp(0.0, tz=timezone.utc),
        wallet_balance=1.0,
        positions={
            s: Position(
                margin=0.0,
                direction=PositionDirection.NONE,
                entry_price=0.0,
                update_time=datetime.fromtimestamp(0.0, tz=timezone.utc),
            )
            for s in target_symbols
        },
        open_orders={s: {} for s in target_symbols},
    )


def create_empty_asset_record():
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


def create_empty_unrealized_changes():
    return pd.Series(index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32)


def create_strategy_code_name() -> str:
    ingredients = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code_name = "".join(random.choice(ingredients) for _ in range(6))
    return code_name
