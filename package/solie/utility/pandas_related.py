import numpy as np
import pandas as pd


def combine_candle_data(
    prior_df: pd.DataFrame, secondary_df: pd.DataFrame
) -> pd.DataFrame:
    df = prior_df.combine_first(secondary_df)
    df = df.sort_index()
    df = df.asfreq("10s")
    df = df.astype(np.float32)
    return df
