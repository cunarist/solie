import talib
import pandas as pd
import numpy as np
import itertools
import threading

from recipe import level_constant
from recipe import thread
from recipe import standardize


def do(observed_data, strategy, compiled_custom_script):

    # ■■■■■ interpolate nans ■■■■■

    observed_data = observed_data.interpolate()

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

    # ■■■■■ return empty indicators if the observed data is empty ■■■■■

    if len(observed_data.dropna()) < 3:
        for column_name, new_indicator in new_indicators.items():
            new_indicator.name = column_name
        indicators = pd.concat(new_indicators.values(), axis="columns")
        return indicators

    # ■■■■■ make individual indicators ■■■■■

    def job(symbol):

        with observed_data_lock:
            if symbol not in observed_data.columns.get_level_values(0):
                return

        if strategy == 0:

            namespace = {
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

        elif strategy == 57:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            moving_average = talib.SMA(sr, 60 * 60 / 10)

            new_indicators[(symbol, "Price", "SMA 60")] = moving_average
            new_indicators[(symbol, "Price", "Combined SMA+")] = moving_average * 1.01
            new_indicators[(symbol, "Price", "Combined SMA-")] = moving_average * 0.99

        elif strategy == 61:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            new_indicators[(symbol, "Price", "SMA 360")] = talib.SMA(sr, 360 * 60 / 10)

            for turn in range(4):
                level = turn + 1
                new_indicators[
                    (symbol, "Price", "SMA 360 .15.10" + ("+" * level))
                ] = new_indicators[(symbol, "Price", "SMA 360")] * (1 + 0.015 * level)
                new_indicators[
                    (symbol, "Price", "SMA 360 .15.10" + ("-" * level))
                ] = new_indicators[(symbol, "Price", "SMA 360")] * (1 - 0.015 * level)

        elif strategy == 64:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            new_indicators[(symbol, "Price", "SMA 20")] = talib.SMA(sr, 20 * 60 / 10)

            for turn in range(5):
                level = turn + 1
                new_indicators[
                    (symbol, "Price", "SMA 20 .01.13" + ("+" * level))
                ] = new_indicators[(symbol, "Price", "SMA 20")] * (
                    1 + 0.001 * level_constant.do(level, 4 / 3)
                )
                new_indicators[
                    (symbol, "Price", "SMA 20 .01.13" + ("-" * level))
                ] = new_indicators[(symbol, "Price", "SMA 20")] * (
                    1 - 0.001 * level_constant.do(level, 4 / 3)
                )

        elif strategy == 65:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            sma_sr = talib.SMA(sr, 20 * 60 / 10)
            new_indicators[(symbol, "Price", "SMA 20")] = sma_sr

            new_indicators[(symbol, "Price", "SMA 20 .01.10+")] = sma_sr * (1 + 0.001)
            new_indicators[(symbol, "Price", "SMA 20 .01.10-")] = sma_sr * (1 - 0.001)

        elif strategy == 89:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            sma_sr = talib.SMA(sr, 1440 * 8 * 60 / 10)
            new_indicators[(symbol, "Price", "SMA 11520")] = sma_sr

        elif strategy == 93:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            dimensions = [1, 4, 16, 64]

            for dimension in dimensions:
                name = str(dimension)
                new_indicators[(symbol, "Price", f"SMA {name}")] = talib.SMA(
                    sr, dimension * 60 / 10
                )

        elif strategy == 95:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            (bbands_up, bbands_middle, _) = talib.BBANDS(sr, 120 * 60 / 10, 2)
            bbands_down = 2 * bbands_middle - bbands_up

            new_indicators[(symbol, "Price", "BBANDS 120+")] = bbands_up
            new_indicators[(symbol, "Price", "BBANDS 120")] = bbands_middle
            new_indicators[(symbol, "Price", "BBANDS 120-")] = bbands_down

        elif strategy == 98:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            moving_average = talib.SMA(sr, 1440 * 8 * 60 / 10)

            new_indicators[(symbol, "Price", "SMA 11520")] = moving_average

        elif strategy == 100:

            with observed_data_lock:
                sr = observed_data[(symbol, "Close")].copy()

            dimensions = [1, 4, 16, 64]

            for dimension in dimensions:
                name = str(dimension)
                sma_sr = talib.SMA(sr, dimension * 60 / 10)
                new_indicators[(symbol, "Price", f"SMA {name}")] = sma_sr

        elif strategy == 107:

            with observed_data_lock:
                sr = observed_data[(symbol, "Volume")].copy()
            volume_sma = talib.SMA(sr, 24 * 60 * 60 / 10) * 10

            new_indicators[(symbol, "Volume", "SMA (#666666)")] = volume_sma

        elif strategy == 110:

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

    thread.map(job, standardize.get_basics()["target_symbols"])

    # ■■■■■ concatenate individual indicators into one ■■■■■

    for column_name, new_indicator in new_indicators.items():
        new_indicator.name = column_name

    indicators = pd.concat(new_indicators.values(), axis="columns")
    indicators = indicators.astype(np.float32)

    return indicators
