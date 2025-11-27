"""Standardized data structure creation utilities."""

import secrets
from datetime import UTC, datetime
from itertools import product

import numpy as np
import pandas as pd

from .data_models import AccountState, Position, PositionDirection


def create_empty_candle_data(target_symbols: list[str]) -> pd.DataFrame:
    """Create empty candle data DataFrame with proper columns."""
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
    """Create empty account state with no positions."""
    return AccountState(
        observed_until=datetime.fromtimestamp(0.0, tz=UTC),
        wallet_balance=1.0,
        positions={
            s: Position(
                margin=0.0,
                direction=PositionDirection.NONE,
                entry_price=0.0,
                update_time=datetime.fromtimestamp(0.0, tz=UTC),
            )
            for s in target_symbols
        },
        open_orders={s: {} for s in target_symbols},
    )


def create_empty_asset_record() -> pd.DataFrame:
    """Create empty asset record DataFrame."""
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
    """Create empty unrealized changes Series."""
    return pd.Series(index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32)


def create_strategy_code_name() -> str:
    """Generate random 6-letter strategy code name."""
    ingredients = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(secrets.choice(ingredients) for _ in range(6))


class Cell[T]:
    """A simple mutable box to hold a value."""

    def __init__(self, value: T) -> None:
        """Initialize box with value."""
        self.value = value
