import pandas as pd


def do(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_index(axis="index")
    df = df.sort_index(axis="columns")
    return df
