import io
from urllib.error import HTTPError
from urllib.request import urlopen

import numpy as np
import pandas as pd


def do(target_tuple: tuple) -> pd.DataFrame | None:
    symbol = target_tuple[0]
    download_type = target_tuple[1]

    if download_type == "daily":
        year_string = format(target_tuple[2], "04")
        month_string = format(target_tuple[3], "02")
        day_string = format(target_tuple[4], "02")
        url = (
            "https://data.binance.vision/static/futures/um/daily/aggTrades"
            + f"/{symbol}/{symbol}-aggTrades"
            + f"-{year_string}-{month_string}-{day_string}.zip"
        )
    elif download_type == "monthly":
        year_string = format(target_tuple[2], "04")
        month_string = format(target_tuple[3], "02")
        url = (
            "https://data.binance.vision/static/futures/um/monthly/aggTrades"
            + f"/{symbol}/{symbol}-aggTrades"
            + f"-{year_string}-{month_string}.zip"
        )
    else:
        raise ValueError("This download type is not supported")

    try:
        zipped_csv_data = io.BytesIO(urlopen(url).read())
    except HTTPError:
        return

    try:
        df = pd.concat(
            pd.read_csv(
                zipped_csv_data,
                compression="zip",
                header=None,
                usecols=[1, 2, 5],
                dtype={1: np.float32, 2: np.float32, 5: np.int64},
                chunksize=10**6,
            )
        )
    except ValueError:
        # when there is a header line in start of the file
        # from august 2022, header is included from binance
        df = pd.concat(
            pd.read_csv(
                zipped_csv_data,
                compression="zip",
                header=0,
                usecols=[1, 2, 5],
                dtype={1: np.float32, 2: np.float32, 5: np.int64},
                chunksize=10**6,
            )
        )
        df = df.rename(columns={"price": 1, "quantity": 2, "transact_time": 5})

    df = df.set_index(5)
    df.index.name = None
    df.index = pd.to_datetime(df.index, unit="ms", utc=True)

    # fill index holes that's smaller than 10 minutes
    temp_sr = pd.Series(0, index=df.index, dtype=np.float32)
    temp_sr = temp_sr.groupby(temp_sr.index).first()
    temp_sr = temp_sr.resample("10s").agg("mean")
    temp_sr = temp_sr.interpolate(limit=60, limit_direction="forward")
    temp_sr = temp_sr.replace(np.nan, 1)
    temp_sr = temp_sr.replace(0, np.nan)
    temp_sr = temp_sr.interpolate(limit=60, limit_direction="backward")
    temp_sr = temp_sr.replace(np.nan, 0)
    temp_sr = temp_sr.replace(1, np.nan)
    temp_sr = temp_sr.dropna()
    valid_index = temp_sr.index

    del temp_sr

    # process data

    close_sr = df[1].resample("10s").agg("last")
    close_sr = close_sr.reindex(valid_index)
    close_sr = close_sr.fillna(method="ffill")
    close_sr = close_sr.astype(np.float32)
    close_sr.name = (symbol, "Close")

    open_sr = df[1].resample("10s").agg("first")
    open_sr = open_sr.reindex(valid_index)
    open_sr = open_sr.fillna(value=close_sr)
    open_sr = open_sr.astype(np.float32)
    open_sr.name = (symbol, "Open")

    high_sr = df[1].resample("10s").agg("max")
    high_sr = high_sr.reindex(valid_index)
    high_sr = high_sr.fillna(value=close_sr)
    high_sr = high_sr.astype(np.float32)
    high_sr.name = (symbol, "High")

    low_sr = df[1].resample("10s").agg("min")
    low_sr = low_sr.reindex(valid_index)
    low_sr = low_sr.fillna(value=close_sr)
    low_sr = low_sr.astype(np.float32)
    low_sr.name = (symbol, "Low")

    volume_sr = df[2].resample("10s").agg("sum")
    volume_sr = volume_sr.reindex(valid_index)
    volume_sr = volume_sr.fillna(value=0)
    volume_sr = volume_sr.astype(np.float32)
    volume_sr.name = (symbol, "Volume")

    del df

    series_list = [open_sr, high_sr, low_sr, close_sr, volume_sr]
    new_df = pd.concat(series_list, axis="columns")

    return new_df
