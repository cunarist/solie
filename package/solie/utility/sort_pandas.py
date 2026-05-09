"""Pandas data sorting utilities."""

from pandas import DataFrame, Series


def sort_data_frame(data: DataFrame) -> DataFrame:
    """Sort DataFrame by index."""
    return data.sort_index()


def sort_series(data: Series) -> Series:
    """Sort Series by index."""
    return data.sort_index()
