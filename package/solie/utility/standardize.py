"""Standardized data structure creation utilities."""

import secrets
from datetime import UTC, datetime

from polars import DataFrame, Float32, Series

from solie.utility import (
    ASSET_RECORD_SCHEMA,
    AccountState,
    Position,
    PositionDirection,
    create_empty_candle_frame_schema,
)


def create_empty_candle_data(target_symbols: list[str]) -> DataFrame:
    """Create empty candle data DataFrame with proper columns."""
    return DataFrame(schema=create_empty_candle_frame_schema(target_symbols))


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


def create_empty_asset_record() -> DataFrame:
    """Create empty asset record DataFrame."""
    return DataFrame(schema=ASSET_RECORD_SCHEMA)


def create_empty_unrealized_changes() -> Series:
    """Create empty unrealized changes Series."""
    return Series("0", [], dtype=Float32)


def create_strategy_code_name() -> str:
    """Generate random 6-letter strategy code name."""
    ingredients = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(secrets.choice(ingredients) for _ in range(6))


class Cell[T]:
    """A simple mutable box to hold a value."""

    def __init__(self, value: T) -> None:
        """Initialize box with value."""
        self.value = value
