import pandas as pd


def do(data: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    if type(data) is pd.DataFrame:
        data = data.sort_index(axis="index")
        data = data.sort_index(axis="columns")
    elif type(data) is pd.Series:
        data = data.sort_index()
    return data
