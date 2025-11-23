import random
from datetime import datetime, timezone
from itertools import product

import numpy as np
import pandas as pd

from .data_models import AccountState, Position, PositionDirection


def create_empty_candle_data(target_symbols: list[str]) -> pd.DataFrame:
    column_pairs = product(
        target_symbols,
        ("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"),
    )
    return pd.DataFrame(
        columns=["/".join(p) for p in column_pairs],
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


def create_empty_asset_record() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "CAUSE",
            "SYMBOL",
            "SIDE",
            "FILL_PRICE",
            "ROLE",
            "MARGIN_RATIO",
            "ORDER_ID",
            "RESULT_ASSET",
        ],
        index=pd.DatetimeIndex([], tz="UTC"),
    )


def create_empty_unrealized_changes() -> pd.Series:
    return pd.Series(index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32)


def create_strategy_code_name() -> str:
    ingredients = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code_name = "".join(random.choice(ingredients) for _ in range(6))
    return code_name


class Cell[T]:
    """A simple mutable box to hold a value."""

    def __init__(self, value: T) -> None:
        self.value = value
