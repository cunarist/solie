from typing import TypeVar

import pandas as pd

T = TypeVar("T", pd.DataFrame, pd.Series)


def do(data: T) -> T:
    if type(data) is pd.DataFrame:
        data = data.sort_index(axis="index")
        data = data.sort_index(axis="columns")
    elif type(data) is pd.Series:
        data = data.sort_index()
    return data
