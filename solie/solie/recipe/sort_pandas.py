import pandas as pd


def data_frame(data: pd.DataFrame) -> pd.DataFrame:
    data = data.sort_index(axis="index")
    data = data.sort_index(axis="columns")
    return data


def series(data: pd.Series) -> pd.Series:
    data = data.sort_index()
    return data
