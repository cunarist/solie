import itertools
from datetime import datetime, timedelta, timezone
from types import CodeType

import numpy as np
import pandas as pd
import pandas_ta as ta


def do(
    target_symbols: list[str],
    candle_data: pd.DataFrame,
    indicators_script: str | CodeType,
    only_last_index: bool = False,
) -> pd.DataFrame:
    # ■■■■■ interpolate nans ■■■■■

    candle_data = candle_data.interpolate()

    # ■■■■■ make dummy row to avoid ta error with all nan series ■■■■■

    if len(candle_data) > 0:
        dummy_index = candle_data.index[-1] + timedelta(seconds=1)
    else:
        dummy_index = datetime.fromtimestamp(0, tz=timezone.utc)

    candle_data.loc[dummy_index, :] = 0.0

    # ■■■■■ basic values ■■■■■

    blank_columns = itertools.product(
        target_symbols,
        ("Price", "Volume", "Abstract"),
        ("Blank",),
    )
    new_indicators: dict[tuple, pd.Series] = {}
    base_index = candle_data.index
    for blank_column in blank_columns:
        new_indicators[blank_column] = pd.Series(
            np.nan,
            index=base_index,
            dtype=np.float32,
        )

    # ■■■■■ make individual indicators ■■■■■

    namespace = {
        "ta": ta,
        "pd": pd,
        "np": np,
        "target_symbols": target_symbols,
        "candle_data": candle_data,
        "new_indicators": new_indicators,
    }
    exec(indicators_script, namespace)
    new_indicators = {k: v for k, v in new_indicators.items() if v is not None}

    # ■■■■■ concatenate individual indicators into one ■■■■■

    for column_name, new_indicator in new_indicators.items():
        new_indicator.name = column_name

    indicators = pd.concat(new_indicators.values(), axis="columns")
    indicators = indicators.astype(np.float32)

    # ■■■■■ remove dummy row ■■■■■

    indicators = indicators.iloc[:-1]

    if only_last_index:
        return indicators.tail(1)
    else:
        return indicators
