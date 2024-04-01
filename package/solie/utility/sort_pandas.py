import pandas as pd


def sort_data_frame(data: pd.DataFrame) -> pd.DataFrame:
    data = data.sort_index()
    return data


def sort_series(data: pd.Series) -> pd.Series:
    data = data.sort_index()
    return data
