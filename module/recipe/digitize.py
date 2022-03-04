import ast
import pandas as pd
import numpy as np


def do(realtime_data):
    # function that converts recarray to 0.1s interval dataframe
    df = pd.DataFrame(realtime_data)

    df = df.set_index("index")
    df.index.name = None
    df.index = df.index.tz_localize("UTC")

    mask = ~df.index.duplicated()
    df = df[mask]

    df = df.resample("100ms").ffill()

    df = df.replace(0, np.nan)
    df = df.fillna(method="ffill")

    original_columns = df.columns
    column_tuples = [ast.literal_eval(name) for name in original_columns]
    df.columns = pd.MultiIndex.from_tuples(column_tuples)

    df = df.sort_index(axis="columns")

    return df
