import numpy as np
import pandas as pd


def do(prior_df: pd.DataFrame, secondary_df: pd.DataFrame) -> pd.DataFrame:
    df = prior_df.combine_first(secondary_df)
    df = df.sort_index()
    df = df.asfreq("10S")
    df = df.astype(np.float32)
    return df
