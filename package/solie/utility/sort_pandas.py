"""Pandas data sorting utilities."""

import pandas as pd


def sort_data_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Sort DataFrame by index."""
    return data.sort_index()


def sort_series(data: pd.Series) -> pd.Series:
    """Sort Series by index."""
    return data.sort_index()
