import numpy as np


def do(prior_df, secondary_df):
    df = prior_df.combine_first(secondary_df)
    df = df.sort_index(axis="index")
    df = df.sort_index(axis="columns")
    df = df.resample("10S").asfreq()
    df = df.astype(np.float32)
    return df
