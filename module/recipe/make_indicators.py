import itertools
from datetime import datetime, timedelta, timezone
from types import CodeType

import numpy as np
import pandas as pd
import talib


def do(**kwargs) -> pd.DataFrame:
    # ■■■■■ get data ■■■■■

    target_symbols = kwargs["target_symbols"]
    candle_data = kwargs["candle_data"]
    indicators_script: str | CodeType = kwargs["indicators_script"]

    # ■■■■■ interpolate nans ■■■■■

    candle_data = candle_data.interpolate()

    # ■■■■■ make dummy row to avoid talib error with all nan series ■■■■■

    if len(candle_data) > 0:
        dummy_index = candle_data.index[-1] + timedelta(seconds=1)
    else:
        dummy_index = datetime.fromtimestamp(0, tz=timezone.utc)

    candle_data.loc[dummy_index] = 0

    # ■■■■■ basic values ■■■■■

    blank_columns = itertools.product(
        target_symbols,
        ("Price", "Volume", "Abstract"),
        ("Blank",),
    )
    new_indicators = {}
    base_index = candle_data.index
    for blank_column in blank_columns:
        new_indicators[blank_column] = pd.Series(
            np.nan,
            index=base_index,
            dtype=np.float32,
        )

    # ■■■■■ make individual indicators ■■■■■

    namespace = {
        "talib": talib,
        "pd": pd,
        "np": np,
        "target_symbols": target_symbols,
        "candle_data": candle_data,
        "new_indicators": new_indicators,
    }
    exec(indicators_script, namespace)

    # ■■■■■ concatenate individual indicators into one ■■■■■

    for column_name, new_indicator in new_indicators.items():
        new_indicator.name = column_name

    indicators = pd.concat(new_indicators.values(), axis="columns")
    indicators = indicators.astype(np.float32)

    # ■■■■■ remove dummy row ■■■■■

    indicators = indicators.iloc[:-1]

    return indicators
