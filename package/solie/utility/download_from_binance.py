from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import NamedTuple
from urllib.request import urlopen
from zipfile import ZipFile

import numpy as np
import pandas as pd

from .data_models import AggregateTrade
from .timing import to_moment

BYTE_CHUNK = 1024 * 1024
RETRY_COUNT = 5
TICK_MS = 10_000


class CsvRow(NamedTuple):
    price: float
    quantity: float
    transact_time: int


class AggTrade(NamedTuple):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class DownloadUnitSize(Enum):
    DAILY = 0
    MONTHLY = 1


class DownloadPreset(NamedTuple):
    symbol: str
    unit_size: DownloadUnitSize
    year: int
    month: int
    day: int = 0  # Valid only when `unit_size` is `DAILY`


def process_csv_line(
    line: str,
    csv_rows: list[CsvRow],
    agg_trades: list[AggTrade],
    current_tick_start: int | None,
) -> int | None:
    """Process a single CSV line and return the new current_tick_start."""
    decoded_line = line.strip()
    if not decoded_line:
        return current_tick_start

    columns = decoded_line.split(",")
    csv_row = CsvRow(
        price=float(columns[1]),
        quantity=float(columns[2]),
        transact_time=int(columns[5]),
    )

    # Calculate which 10-second tick this row belongs to
    row_tick_start = (csv_row.transact_time // TICK_MS) * TICK_MS

    # If we moved to a new tick, process the previous tick
    if current_tick_start is not None and row_tick_start != current_tick_start:
        finalize_tick(csv_rows, agg_trades, current_tick_start, row_tick_start)
        csv_rows.clear()

    csv_rows.append(csv_row)
    return row_tick_start


def finalize_tick(
    csv_rows: list[CsvRow],
    agg_trades: list[AggTrade],
    current_tick_start: int,
    next_tick_start: int | None = None,
) -> None:
    """Finalize the current tick by creating a candle and filling gaps."""
    if not csv_rows:
        return

    # Create candle from accumulated rows
    open_price = csv_rows[0].price
    high_price = max(row.price for row in csv_rows)
    low_price = min(row.price for row in csv_rows)
    close_price = csv_rows[-1].price
    volume = sum(row.quantity for row in csv_rows)

    agg_trades.append(
        AggTrade(
            time=current_tick_start,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )
    )

    # Fill gaps if there are missing ticks
    if (
        next_tick_start
        and agg_trades
        and next_tick_start > current_tick_start + TICK_MS
    ):
        last_close = agg_trades[-1].close
        gap_tick = current_tick_start + TICK_MS
        while gap_tick < next_tick_start:
            new_agg_trade = AggTrade(
                time=gap_tick,
                open=last_close,
                high=last_close,
                low=last_close,
                close=last_close,
                volume=0.0,
            )
            agg_trades.append(new_agg_trade)
            gap_tick += TICK_MS


def download_aggtrade_data(
    download_target: DownloadPreset, download_dir: Path
) -> pd.DataFrame | None:
    symbol = download_target.symbol
    unit_size = download_target.unit_size

    # Create download URL and file name
    match unit_size:
        case DownloadUnitSize.DAILY:
            year_string = format(download_target.year, "04")
            month_string = format(download_target.month, "02")
            day_string = format(download_target.day, "02")
            url = (
                "https://data.binance.vision/data/futures/um/daily/aggTrades"
                f"/{symbol}/{symbol}-aggTrades"
                f"-{year_string}-{month_string}-{day_string}.zip"
            )
            file_name = f"{symbol}-{year_string}-{month_string}-{day_string}.zip"
        case DownloadUnitSize.MONTHLY:
            year_string = format(download_target.year, "04")
            month_string = format(download_target.month, "02")
            url = (
                "https://data.binance.vision/data/futures/um/monthly/aggTrades"
                f"/{symbol}/{symbol}-aggTrades"
                f"-{year_string}-{month_string}.zip"
            )
            file_name = f"{symbol}-{year_string}-{month_string}.zip"
    zip_file_path = download_dir / file_name

    # Download to a temporary file.
    # Download in chunks to avoid memory issues.
    did_download = False
    for _ in range(RETRY_COUNT):
        try:
            with urlopen(url) as response:
                with open(zip_file_path, "wb") as f:
                    while True:
                        chunk = response.read(BYTE_CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
            did_download = True
            break
        except Exception:
            continue

    if not did_download:
        return None

    # Check if CSV has header by reading first line
    has_header = False
    with ZipFile(zip_file_path, "r") as zip_ref:
        csv_filename = zip_ref.namelist()[0]
        with zip_ref.open(csv_filename) as csv_file:
            first_line = csv_file.readline().decode("ascii")
            has_header = "price" in first_line.lower()

    csv_rows = list[CsvRow]()
    agg_trades: list[AggTrade] = []
    current_tick_start: int | None = None

    with ZipFile(zip_file_path, "r") as zip_ref:
        csv_filename = zip_ref.namelist()[0]
        with zip_ref.open(csv_filename) as csv_file:
            # Skip header if exists
            if has_header:
                csv_file.readline()

            # Read and process CSV lines
            for line in csv_file:
                decoded_line = line.decode("ascii")
                current_tick_start = process_csv_line(
                    decoded_line, csv_rows, agg_trades, current_tick_start
                )

            # Process the last tick
            if csv_rows and current_tick_start is not None:
                finalize_tick(csv_rows, agg_trades, current_tick_start)

    # Convert to DataFrame
    if not agg_trades:
        return None

    df = pd.DataFrame(agg_trades)
    df = df.set_index("time")
    df.index.name = None
    df.index = pd.to_datetime(df.index, unit="ms", utc=True)

    # Rename columns to match expected format
    df = df.rename(
        columns={
            "open": f"{symbol}/OPEN",
            "high": f"{symbol}/HIGH",
            "low": f"{symbol}/LOW",
            "close": f"{symbol}/CLOSE",
            "volume": f"{symbol}/VOLUME",
        }
    )

    # Convert to float32 for memory efficiency
    df = df.astype(np.float32)

    return df


def fill_holes_with_aggtrades(
    symbol: str,
    recent_candle_data: pd.DataFrame,
    aggtrades: dict[int, AggregateTrade],
    moment_to_fill_from: datetime,
    last_fetched_time: datetime,
) -> pd.DataFrame:
    fill_moment = moment_to_fill_from

    last_fetched_moment = to_moment(last_fetched_time)
    while fill_moment < last_fetched_moment:
        block_start = fill_moment
        block_end = fill_moment + timedelta(seconds=10)

        aggtrade_prices: list[float] = []
        aggtrade_volumes: list[float] = []
        for _, aggtrade in sorted(aggtrades.items()):
            # sorted by time
            aggtrade_time = datetime.fromtimestamp(
                aggtrade.timestamp / 1000, tz=timezone.utc
            )
            if block_start <= aggtrade_time < block_end:
                aggtrade_prices.append(aggtrade.price)
                aggtrade_volumes.append(aggtrade.volume)

        can_write = True

        if len(aggtrade_prices) == 0:
            # when there are no trades
            inspect_sr = recent_candle_data[f"{symbol}/CLOSE"]
            inspect_sr = inspect_sr.sort_index()
            last_prices = inspect_sr[:fill_moment].dropna()
            if len(last_prices) == 0:
                # when there are no previous data
                # because new data folder was created
                can_write = False
                last_price = 0
            else:
                last_price = last_prices.iloc[-1]
            open_price = last_price
            high_price = last_price
            low_price = last_price
            close_price = last_price
            sum_volume = 0
        else:
            open_price = aggtrade_prices[0]
            high_price = max(aggtrade_prices)
            low_price = min(aggtrade_prices)
            close_price = aggtrade_prices[-1]
            sum_volume = sum(aggtrade_volumes)

        if can_write:
            column = f"{symbol}/OPEN"
            recent_candle_data.loc[fill_moment, column] = np.float32(open_price)
            column = f"{symbol}/HIGH"
            recent_candle_data.loc[fill_moment, column] = np.float32(high_price)
            column = f"{symbol}/LOW"
            recent_candle_data.loc[fill_moment, column] = np.float32(low_price)
            column = f"{symbol}/CLOSE"
            recent_candle_data.loc[fill_moment, column] = np.float32(close_price)
            column = f"{symbol}/VOLUME"
            recent_candle_data.loc[fill_moment, column] = np.float32(sum_volume)

        fill_moment += timedelta(seconds=10)

    recent_candle_data = recent_candle_data.sort_index(axis="index")
    recent_candle_data = recent_candle_data.sort_index(axis="columns")

    return recent_candle_data
