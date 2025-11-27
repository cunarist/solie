"""Pandas utility functions."""

import numpy as np
import pandas as pd


def combine_candle_data(dataframes: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine multiple candle dataframes into one."""
    if len(dataframes) == 0:
        msg = "At least one DataFrame is required"
        raise ValueError(msg)

    stacked = pd.concat(dataframes)
    df = stacked.groupby(level=0).first()

    df = df.sort_index()
    df = df.asfreq("10s")
    return df.astype(np.float32)
