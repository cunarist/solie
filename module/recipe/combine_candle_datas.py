import numpy as np


def do(prior_df, secondary_df):
    df = prior_df.combine_first(secondary_df)
    df = df.sort_index()
    df = df.asfreq("10S")
    df = df.astype(np.float32)
    return df
