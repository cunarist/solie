"""Historical market data download from Binance."""

from asyncio import sleep
from datetime import UTC, datetime, timedelta
from enum import Enum
from logging import getLogger
from pathlib import Path
from typing import NamedTuple
from zipfile import ZipFile, is_zipfile

import aiofiles
import aiofiles.os
import aiohttp
import numpy as np
import pandas as pd

from solie.common import spawn_blocking
from solie.utility import AggregateTrade, to_moment

logger = getLogger(__name__)

BYTE_CHUNK = 1024 * 1024
RETRY_COUNT = 10
RETRY_INTERVAL = 2
TICK_MS = 10_000
COMMA_BYTE = b","


class CsvRow(NamedTuple):
    """Single row from Binance aggregate trade CSV."""

    price: float
    quantity: float
    transact_time: int


class Candle(NamedTuple):
    """Candlestick data aggregated from trades."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class DownloadUnitSize(Enum):
    """Time unit for historical data downloads."""

    DAILY = 0
    MONTHLY = 1


class DownloadPreset(NamedTuple):
    """Configuration for downloading historical data."""

    symbol: str
    unit_size: DownloadUnitSize
    year: int
    month: int
    day: int = 0  # Valid only when `unit_size` is `DAILY`


class UnsortedCsvError(Exception):
    """Exception raised when CSV file has unsorted timestamps."""


class LastTickStatus(NamedTuple):
    """Status of the last processed tick during CSV parsing."""

    current_tick_start: int
    prev_transact_time: int


def process_csv_line(
    line: bytes,
    csv_rows: list[CsvRow],
    agg_trades: list[Candle],
    last_tick_status: LastTickStatus | None,
) -> LastTickStatus:
    """Process a single CSV line and return the new tick status.

    We use raw byte parsing for performance.
    """
    if last_tick_status is None:
        current_tick_start, prev_transact_time = None, None
    else:
        current_tick_start, prev_transact_time = last_tick_status

    # Split the line by commas
    columns = line.split(COMMA_BYTE)

    # Extract only the needed values for performance
    price = float(columns[1])
    quantity = float(columns[2])
    transact_time = int(columns[5])

    # Check for timestamp ordering
    if prev_transact_time is not None and transact_time < prev_transact_time:
        raise UnsortedCsvError

    # Calculate which 10-second tick this row belongs to
    row_tick_start = (transact_time // TICK_MS) * TICK_MS

    # If we moved to a new tick, process the previous tick
    if current_tick_start is not None and row_tick_start != current_tick_start:
        finalize_tick(csv_rows, agg_trades, current_tick_start, row_tick_start)
        csv_rows.clear()

    # Record the current status.
    # Do not write keyword arguments that impact performance.
    csv_rows.append(CsvRow(price, quantity, transact_time))
    return LastTickStatus(row_tick_start, transact_time)


def finalize_tick(
    csv_rows: list[CsvRow],
    agg_trades: list[Candle],
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
        Candle(
            time=current_tick_start,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        ),
    )

    # Fill gaps if there are missing ticks
    if (
        next_tick_start is not None
        and agg_trades
        and next_tick_start > current_tick_start + TICK_MS
    ):
        last_close = agg_trades[-1].close
        gap_tick = current_tick_start + TICK_MS
        while gap_tick < next_tick_start:
            new_agg_trade = Candle(
                time=gap_tick,
                open=last_close,
                high=last_close,
                low=last_close,
                close=last_close,
                volume=0.0,
            )
            agg_trades.append(new_agg_trade)
            gap_tick += TICK_MS


async def download_aggtrade_csv(
    download_target: DownloadPreset,
    download_dir: Path,
) -> Path | None:
    """Download the aggtrade CSV file from Binance and return the ZIP file path."""
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
            file_name = f"{symbol}-{year_string}-{month_string}-{day_string}"
        case DownloadUnitSize.MONTHLY:
            year_string = format(download_target.year, "04")
            month_string = format(download_target.month, "02")
            url = (
                "https://data.binance.vision/data/futures/um/monthly/aggTrades"
                f"/{symbol}/{symbol}-aggTrades"
                f"-{year_string}-{month_string}.zip"
            )
            file_name = f"{symbol}-{year_string}-{month_string}"

    # Prepare download file path
    download_file_path = download_dir / f"{file_name}"

    # Download to a temporary file.
    # Download in chunks to avoid memory issues.
    did_download = False
    for _ in range(RETRY_COUNT):
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(url) as response,
                aiofiles.open(download_file_path, "wb") as file,
            ):
                while True:
                    chunk = await response.content.read(BYTE_CHUNK)
                    if not chunk:
                        break
                    await file.write(chunk)
            did_download = True
            break
        except Exception:
            logger.debug("Download attempt failed, retrying")
            await sleep(RETRY_INTERVAL)
            continue

    # Check if download was successful
    if not did_download:
        return None

    # Check if the file is actually a zip file
    if not await spawn_blocking(is_zipfile, download_file_path):
        return None

    # Rename to .zip extension
    zip_file_path = download_dir / f"{file_name}.zip"
    await aiofiles.os.rename(download_file_path, zip_file_path)
    return zip_file_path


def sort_aggtrade_csv(zip_file_path: Path, has_header: bool) -> None:
    """Sort CSV by transact_time and overwrite in ZIP.

    Rarely, Binance provides unsorted CSV files with mixed transact time order.
    """
    # Read CSV from ZIP
    with ZipFile(zip_file_path, "r") as zip_ref:
        csv_filename = zip_ref.namelist()[0]
        with zip_ref.open(csv_filename, "r") as csv_file:
            df = pd.read_csv(csv_file, header=0 if has_header else None)

    # Sort by transact_time (column index 5)
    df = df.sort_values(by=df.columns[5])

    # Write sorted CSV back to ZIP
    with (
        ZipFile(zip_file_path, "w") as zip_ref,
        zip_ref.open(csv_filename, "w", force_zip64=True) as csv_file,
    ):
        df.to_csv(csv_file, index=False, header=has_header)


def check_header(zip_file_path: Path) -> bool:
    """Check if the CSV file inside the ZIP has a header.

    Some Binance CSV files include headers, while others do not.
    """
    with ZipFile(zip_file_path, "r") as zip_ref:
        csv_filename = zip_ref.namelist()[0]
        with zip_ref.open(csv_filename, "r") as csv_file:
            first_line = csv_file.readline()
            return b"price" in first_line


def process_csv_lines(
    zip_file_path: Path,
    has_header: bool,
    preset: DownloadPreset,
) -> pd.DataFrame | None:
    """Process CSV lines and check for sorting."""
    with ZipFile(zip_file_path, "r") as zip_ref:
        csv_filename = zip_ref.namelist()[0]
        with zip_ref.open(csv_filename, "r") as csv_file:
            # Skip header if exists
            if has_header:
                csv_file.readline()

            # Read and process CSV lines
            csv_rows: list[CsvRow] = []
            agg_trades: list[Candle] = []
            last_tick_status: LastTickStatus | None = None
            for line in csv_file:
                last_tick_status = process_csv_line(
                    line,
                    csv_rows,
                    agg_trades,
                    last_tick_status,
                )

            # Process the last tick
            if csv_rows and last_tick_status is not None:
                finalize_tick(csv_rows, agg_trades, last_tick_status.current_tick_start)

            # If no aggregate trades were processed, return None
            if not agg_trades:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(agg_trades)

            # Set time index
            df = df.set_index("time")
            df.index.name = None
            df.index = pd.to_datetime(df.index, unit="ms", utc=True)

            # Rename columns to match expected format
            symbol = preset.symbol
            df = df.rename(
                columns={
                    "open": f"{symbol}/OPEN",
                    "high": f"{symbol}/HIGH",
                    "low": f"{symbol}/LOW",
                    "close": f"{symbol}/CLOSE",
                    "volume": f"{symbol}/VOLUME",
                },
            )

            # Convert to float32 for memory efficiency
            return df.astype(np.float32)


def process_aggtrade_csv(
    preset: DownloadPreset,
    zip_file_path: Path,
) -> pd.DataFrame | None:
    """Process the downloaded aggtrade CSV file from Binance.

    Convert it into a DataFrame of aggregated trades.
    This is a blocking function that can take tens of minutes.
    """
    has_header = check_header(zip_file_path)
    try:
        df = process_csv_lines(zip_file_path, has_header, preset)
    except UnsortedCsvError:
        sort_aggtrade_csv(zip_file_path, has_header)
        df = process_csv_lines(zip_file_path, has_header, preset)

    return df


def fill_holes_with_aggtrades(
    symbol: str,
    recent_candle_data: pd.DataFrame,
    aggtrades: dict[int, AggregateTrade],
    moment_to_fill_from: datetime,
    last_fetched_time: datetime,
) -> pd.DataFrame:
    """Fill missing candle data using aggregate trade information."""
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
                aggtrade.timestamp / 1000,
                tz=UTC,
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
    return recent_candle_data.sort_index(axis="columns")
