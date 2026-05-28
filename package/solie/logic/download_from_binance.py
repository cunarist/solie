"""Historical market data download from Binance."""

import sqlite3
from asyncio import sleep
from collections.abc import Iterable, Iterator
from enum import Enum
from logging import getLogger
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NamedTuple
from zipfile import ZipFile, is_zipfile

import aiofiles
import aiofiles.os
from aiohttp import ClientSession

from solie import utility
from solie.common import spawn_blocking
from solie.utility import SQLITE_TIMEOUT, CandleRow

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
                ClientSession() as session,
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


def parse_csv_line(line: bytes) -> CsvRow:
    """Parse the aggregate trade fields needed for candle creation."""
    columns = line.split(COMMA_BYTE)
    return CsvRow(
        price=float(columns[1]),
        quantity=float(columns[2]),
        transact_time=int(columns[5]),
    )


def iter_csv_rows(zip_file_path: Path) -> Iterator[CsvRow]:
    """Iterate parsed Binance aggregate-trade rows from a ZIP CSV file."""
    with ZipFile(zip_file_path, "r") as zip_ref:
        csv_filename = zip_ref.namelist()[0]
        with zip_ref.open(csv_filename, "r") as csv_file:
            first_line = csv_file.readline()
            if first_line and b"price" not in first_line:
                yield parse_csv_line(first_line)
            for line in csv_file:
                yield parse_csv_line(line)


def iter_candle_rows(rows: Iterable[CsvRow]) -> Iterator[CandleRow]:
    """Aggregate sorted aggregate trades into streamed 10-second candle rows."""
    current_tick_start: int | None = None
    prev_transact_time: int | None = None
    open_price = 0.0
    high_price = 0.0
    low_price = 0.0
    close_price = 0.0
    volume = 0.0

    for row in rows:
        if prev_transact_time is not None and row.transact_time < prev_transact_time:
            raise UnsortedCsvError

        row_tick_start = (row.transact_time // TICK_MS) * TICK_MS
        if current_tick_start is None:
            current_tick_start = row_tick_start
            open_price = row.price
            high_price = row.price
            low_price = row.price
            close_price = row.price
            volume = row.quantity
        elif row_tick_start == current_tick_start:
            high_price = max(high_price, row.price)
            low_price = min(low_price, row.price)
            close_price = row.price
            volume += row.quantity
        else:
            yield CandleRow(
                current_tick_start,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
            )
            gap_tick = current_tick_start + TICK_MS
            while gap_tick < row_tick_start:
                yield CandleRow(
                    gap_tick,
                    close_price,
                    close_price,
                    close_price,
                    close_price,
                    0.0,
                )
                gap_tick += TICK_MS
            current_tick_start = row_tick_start
            open_price = row.price
            high_price = row.price
            low_price = row.price
            close_price = row.price
            volume = row.quantity

        prev_transact_time = row.transact_time

    if current_tick_start is not None:
        yield CandleRow(
            current_tick_start,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
        )


def iter_sorted_csv_rows(
    zip_file_path: Path,
) -> Iterator[CsvRow]:
    """Use temporary SQLite storage to sort rare unsorted aggregate-trade files."""
    with TemporaryDirectory() as directory:
        filepath = Path(directory) / "aggtrades.sqlite"
        with sqlite3.connect(filepath, timeout=SQLITE_TIMEOUT) as connection:
            connection.execute("PRAGMA synchronous = OFF")
            connection.execute("PRAGMA temp_store = FILE")
            connection.execute(
                """
                CREATE TABLE trades (
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    transact_time INTEGER NOT NULL
                )
                """,
            )
            for row in iter_csv_rows(zip_file_path):
                connection.execute(
                    """
                    INSERT INTO trades(price, quantity, transact_time)
                    VALUES (?, ?, ?)
                    """,
                    row,
                )

            connection.commit()
            connection.execute(
                "CREATE INDEX trades_transact_time ON trades(transact_time)",
            )
            connection.commit()

            cursor = connection.execute(
                """
                SELECT price, quantity, transact_time
                FROM trades
                ORDER BY transact_time
                """,
            )
            try:
                for price, quantity, transact_time in cursor:
                    yield CsvRow(
                        price=float(price),
                        quantity=float(quantity),
                        transact_time=int(transact_time),
                    )
            finally:
                cursor.close()


def write_aggtrade_csv_to_candle_store(
    preset: DownloadPreset,
    zip_file_path: Path,
    candle_rootpath: Path,
) -> int:
    """Process the downloaded aggtrade CSV file from Binance.

    Convert it into streamed 10-second candle rows and persist them directly
    into per-symbol, per-year SQLite candle files.
    This is a blocking function that can take tens of minutes.
    """
    try:
        return utility.write_candle_rows(
            candle_rootpath,
            preset.symbol,
            iter_candle_rows(iter_csv_rows(zip_file_path)),
        )
    except UnsortedCsvError:
        logger.warning(
            "Downloaded aggregate trades were unsorted for %s %04d-%02d",
            preset.symbol,
            preset.year,
            preset.month,
        )

    return utility.write_candle_rows(
        candle_rootpath,
        preset.symbol,
        iter_candle_rows(iter_sorted_csv_rows(zip_file_path)),
    )

