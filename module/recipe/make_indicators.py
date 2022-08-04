import itertools
import threading
from datetime import timedelta

import talib
import pandas as pd
import numpy as np

from module import thread_toss
from module.recipe import standardize


def do(observed_data, strategy, compiled_custom_script):
    # ■■■■■ interpolate nans ■■■■■

    observed_data = observed_data.interpolate()

    # ■■■■■ make dummy row to avoid talib error with all nan series ■■■■■

    last_index = observed_data.index[-1]
    observed_data.loc[last_index + timedelta(seconds=1)] = 0

    # ■■■■■ basic values ■■■■■

    observed_data_lock = threading.Lock()
    blank_columns = itertools.product(
        standardize.get_basics()["target_symbols"],
        ("Price", "Volume", "Abstract"),
        ("Blank",),
    )
    new_indicators = {}
    base_index = observed_data.index
    for blank_column in blank_columns:
        new_indicators[blank_column] = pd.Series(
            np.nan,
            index=base_index,
            dtype=np.float32,
        )

    # ■■■■■ make individual indicators ■■■■■

    def job(symbol):
        with observed_data_lock:
            if symbol not in observed_data.columns.get_level_values(0):
                return

        if strategy == 0:
            namespace = {
                "talib": talib,
                "pd": pd,
                "np": np,
                "symbol": symbol,
                "observed_data": observed_data,
                "observed_data_lock": observed_data_lock,
                "new_indicators": new_indicators,
            }

            exec(compiled_custom_script, namespace)

        elif strategy == 1:
            pass

        elif strategy == 2:
            pass

        elif strategy == 3:
            border = 0.5  # percent

            with observed_data_lock:
                close = observed_data[(symbol, "Close")].copy()

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

            with observed_data_lock:
                volume = observed_data[(symbol, "Volume")].copy()

            fast_volume_sma = talib.SMA(volume, 10 * 60 / 10)
            slow_volume_sma = talib.SMA(volume, 360 * 60 / 10)

            calmness = (slow_volume_sma / fast_volume_sma) ** 2
            calmness = calmness.fillna(value=1)
            calmness[calmness > 4] = 4
            new_indicators[(symbol, "Abstract", "Calmness (#FF8888)")] = calmness

    thread_toss.map(job, standardize.get_basics()["target_symbols"])

    # ■■■■■ concatenate individual indicators into one ■■■■■

    for column_name, new_indicator in new_indicators.items():
        new_indicator.name = column_name

    indicators = pd.concat(new_indicators.values(), axis="columns")
    indicators = indicators.astype(np.float32)

    # ■■■■■ remove dummy row ■■■■■

    indicators = indicators.iloc[:-1]

    return indicators
