import io
from dataclasses import dataclass
from urllib.request import urlopen

import numpy as np
import pandas as pd


@dataclass
class DownloadPreset:
    symbol: str
    unit_size: str  # "daily" or "monthly"
    year: int
    month: int
    day: int = 0  # Valid only when `unit_size` is "daily"


def download_aggtrade_data(download_target: DownloadPreset) -> pd.DataFrame | None:
    symbol = download_target.symbol
    unit_size = download_target.unit_size

    if unit_size == "daily":
        year_string = format(download_target.year, "04")
        month_string = format(download_target.month, "02")
        day_string = format(download_target.day, "02")
        url = (
            "https://data.binance.vision/data/futures/um/daily/aggTrades"
            + f"/{symbol}/{symbol}-aggTrades"
            + f"-{year_string}-{month_string}-{day_string}.zip"
        )
    elif unit_size == "monthly":
        year_string = format(download_target.year, "04")
        month_string = format(download_target.month, "02")
        url = (
            "https://data.binance.vision/data/futures/um/monthly/aggTrades"
            + f"/{symbol}/{symbol}-aggTrades"
            + f"-{year_string}-{month_string}.zip"
        )
    else:
        raise ValueError("This download type is not supported")

    zipped_csv_data = None
    for _ in range(5):
        try:
            zipped_csv_data = io.BytesIO(urlopen(url).read())
            break
        except Exception:
            pass

    if zipped_csv_data is None:
        return

    try:
        df: pd.DataFrame = pd.concat(
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
        df: pd.DataFrame = pd.concat(
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

    close_sr: pd.Series = df[1].resample("10s").agg("last")  # type: ignore
    close_sr = close_sr.reindex(valid_index)
    close_sr = close_sr.ffill()
    close_sr = close_sr.astype(np.float32)
    close_sr.name = (symbol, "Close")

    open_sr: pd.Series = df[1].resample("10s").agg("first")  # type: ignore
    open_sr = open_sr.reindex(valid_index)
    open_sr = open_sr.fillna(value=close_sr)
    open_sr = open_sr.astype(np.float32)
    open_sr.name = (symbol, "Open")

    high_sr: pd.Series = df[1].resample("10s").agg("max")  # type: ignore
    high_sr = high_sr.reindex(valid_index)
    high_sr = high_sr.fillna(value=close_sr)
    high_sr = high_sr.astype(np.float32)
    high_sr.name = (symbol, "High")

    low_sr: pd.Series = df[1].resample("10s").agg("min")  # type: ignore
    low_sr = low_sr.reindex(valid_index)
    low_sr = low_sr.fillna(value=close_sr)
    low_sr = low_sr.astype(np.float32)
    low_sr.name = (symbol, "Low")

    volume_sr: pd.Series = df[2].resample("10s").agg("sum")  # type: ignore
    volume_sr = volume_sr.reindex(valid_index)
    volume_sr = volume_sr.fillna(value=0)
    volume_sr = volume_sr.astype(np.float32)
    volume_sr.name = (symbol, "Volume")

    del df

    series_list = [open_sr, high_sr, low_sr, close_sr, volume_sr]
    new_df = pd.concat(series_list, axis="columns")

    return new_df
