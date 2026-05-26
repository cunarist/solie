"""Tabular sorting utilities."""

from polars import DataFrame, Series


def sort_data_frame(data: DataFrame) -> DataFrame:
    """Sort DataFrame by timestamp when present."""
    if "timestamp" in data.columns:
        return data.sort("timestamp")
    return data


def sort_series(data: Series) -> Series:
    """Return Series unchanged because Polars Series has no index."""
    return data
