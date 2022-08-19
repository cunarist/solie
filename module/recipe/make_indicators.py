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
    strategy_code = kwargs["strategy_code"]
    compiled_custom_script = kwargs["compiled_custom_script"]

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

        if strategy_code == "SLSLDS":
            border = 0.5  # percent

            with datalocks.hold("candle_data_during_indicator_creation"):
                close = candle_data[(symbol, "Close")].copy()

            dimensions = [1, 4, 16, 64]

            combined = pd.Series(0, index=close.index, dtype=np.float32)
            for dimension in dimensions:
                combined += talib.SMA(close, dimension * 60 / 10)
            combined /= len(dimensions)

            new_indicators[(symbol, "Price", "Combined")] = combined

            diff = (close - combined) / combined * 100
            diff[(diff < border) & (diff > -border)] = 0
            diff[diff > border] = diff - border
            diff[diff < -border] = diff + border
            new_indicators[(symbol, "Abstract", "Diff")] = diff

            diff_sum = diff.rolling(int(600 / 10)).sum() / 6  # percent*minute
            new_indicators[(symbol, "Abstract", "Diff Sum (#BB00FF)")] = diff_sum

            with datalocks.hold("candle_data_during_indicator_creation"):
                volume = candle_data[(symbol, "Volume")].copy()

            fast_volume_sma = talib.SMA(volume, 10 * 60 / 10)
            slow_volume_sma = talib.SMA(volume, 360 * 60 / 10)

            calmness = (slow_volume_sma / fast_volume_sma) ** 2
            calmness = calmness.fillna(value=1)
            calmness[calmness > 4] = 4
            new_indicators[(symbol, "Abstract", "Calmness (#FF8888)")] = calmness

        elif strategy_code == "MKRNDM":
            pass

        elif strategy_code == "CSMSTR":
            namespace = {
                "talib": talib,
                "pd": pd,
                "np": np,
                "symbol": symbol,
                "candle_data": candle_data,
                "datalocks": datalocks,
                "new_indicators": new_indicators,
            }

            exec(compiled_custom_script, namespace)

    thread_toss.map(job, target_symbols)

    # ■■■■■ concatenate individual indicators into one ■■■■■

    for column_name, new_indicator in new_indicators.items():
        new_indicator.name = column_name

    indicators = pd.concat(new_indicators.values(), axis="columns")
    indicators = indicators.astype(np.float32)

    # ■■■■■ remove dummy row ■■■■■

    indicators = indicators.iloc[:-1]

    return indicators
