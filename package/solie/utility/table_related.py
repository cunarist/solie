"""Tabular utility functions."""

import polars as pl
from polars import DataFrame


def combine_candle_data(dataframes: list[DataFrame]) -> DataFrame:
    """Combine multiple candle dataframes into one."""
    if len(dataframes) == 0:
        msg = "At least one DataFrame is required"
        raise ValueError(msg)

    # Temporary bridge for legacy callers; full candle storage is moving to
    # per-symbol, per-year SQLite files.
    return pl.concat(dataframes)
