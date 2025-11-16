import numpy as np
import pandas as pd


def combine_candle_data(dataframes: list[pd.DataFrame]) -> pd.DataFrame:
    if len(dataframes) == 0:
        raise ValueError("At least one DataFrame is required")

    stacked = pd.concat(dataframes)
    df = stacked.groupby(level=0).first()

    df = df.sort_index()
    df = df.asfreq("10s")
    df = df.astype(np.float32)
    return df
