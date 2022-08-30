import itertools
from datetime import timedelta

import talib
import pandas as pd
import numpy as np

from module import thread_toss
from module.recipe import datalocks


def do(**kwargs):
    # ■■■■■ get data ■■■■■

    target_symbols = kwargs["target_symbols"]
    candle_data = kwargs["candle_data"]
    compiled_indicators_script = kwargs["compiled_indicators_script"]

    # ■■■■■ interpolate nans ■■■■■

    candle_data = candle_data.interpolate()

    # ■■■■■ make dummy row to avoid talib error with all nan series ■■■■■

    last_index = candle_data.index[-1]
    candle_data.loc[last_index + timedelta(seconds=1)] = 0

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

    def job(symbol):
        with datalocks.hold("candle_data_during_indicator_creation"):
            if symbol not in candle_data.columns.get_level_values(0):
                return

        namespace = {
            "talib": talib,
            "pd": pd,
            "np": np,
            "symbol": symbol,
            "candle_data": candle_data,
            "datalocks": datalocks,
            "new_indicators": new_indicators,
        }

        exec(compiled_indicators_script, namespace)

    thread_toss.map(job, target_symbols)

    # ■■■■■ concatenate individual indicators into one ■■■■■

    for column_name, new_indicator in new_indicators.items():
        new_indicator.name = column_name

    indicators = pd.concat(new_indicators.values(), axis="columns")
    indicators = indicators.astype(np.float32)

    # ■■■■■ remove dummy row ■■■■■

    indicators = indicators.iloc[:-1]

    return indicators
