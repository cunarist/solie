"""SQLite-backed candle data storage."""

import functools
import math
import os
import sqlite3
from asyncio import Lock, get_running_loop
from collections.abc import AsyncIterator, Iterable
from contextlib import AsyncExitStack, ExitStack
from datetime import UTC, datetime
from logging import getLogger
from pathlib import Path
from sqlite3 import Connection, OperationalError
from typing import NamedTuple, Self

import aiofiles.os
import aiosqlite
import yoyo
from aiosqlite import Connection as AsyncConnection
from yoyo.exceptions import LockTimeout

from solie.common import PACKAGE_PATH

logger = getLogger(__name__)

VALID_CANDLE_CONDITION = """
open > 0
AND high > 0
AND low > 0
AND close > 0
AND volume >= 0
AND high >= low
AND open >= low
AND open <= high
AND close >= low
AND close <= high
"""
SQLITE_TIMEOUT = 30.0
SQLITE_WRITE_PRAGMAS = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 5000",
)
SELECT_CANDLE_SQL = """
SELECT timestamp, open, high, low, close, volume
FROM candles
WHERE timestamp = ?
AND """ + VALID_CANDLE_CONDITION
SELECT_LATEST_CANDLE_SQL = """
SELECT timestamp, open, high, low, close, volume
FROM candles
WHERE timestamp < ?
AND """ + VALID_CANDLE_CONDITION + """
ORDER BY timestamp DESC
LIMIT 1
"""
SELECT_CANDLE_RANGE_SQL = """
SELECT timestamp, open, high, low, close, volume
FROM candles
WHERE timestamp >= ?
AND timestamp <= ?
AND """ + VALID_CANDLE_CONDITION + """
ORDER BY timestamp
"""
COUNT_CANDLE_RANGE_SQL = """
SELECT COUNT(*)
FROM candles
WHERE timestamp >= ?
AND timestamp <= ?
AND """ + VALID_CANDLE_CONDITION
COUNT_ALL_CANDLES_SQL = """
SELECT COUNT(*)
FROM candles
WHERE """ + VALID_CANDLE_CONDITION
SELECT_TIMESTAMP_BOUNDS_SQL = """
SELECT MIN(timestamp), MAX(timestamp)
FROM candles
WHERE """ + VALID_CANDLE_CONDITION
DELETE_INVALID_CANDLES_SQL = """
DELETE FROM candles
WHERE NOT (""" + VALID_CANDLE_CONDITION + """)
"""
UPSERT_CANDLE_SQL = """
INSERT INTO candles(timestamp, open, high, low, close, volume)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(timestamp) DO UPDATE SET
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume
"""


class CandleRow(NamedTuple):
    """Single 10-second candle row."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleDataKey(NamedTuple):
    """Identifies one symbol-year candle database."""

    symbol: str
    year: int


class TimestampBounds(NamedTuple):
    """First and last millisecond timestamps in a candle range."""

    first: int
    last: int


class CandleData:
    """SQLite storage for one symbol-year's candle data."""

    def __init__(self, key: CandleDataKey, filepath: Path) -> None:
        """Initialize one symbol-year database wrapper."""
        self.key = key
        self.filepath = filepath
        self._connection: AsyncConnection | None = None
        self._access_lock = Lock()

    async def __aenter__(self) -> Self:
        """Open the database for context-manager use."""
        await self._open()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close the database for context-manager use."""
        await self._close()

    async def _open(self) -> None:
        """Open this symbol's database and apply migrations."""
        async with self._access_lock:
            if self._connection is not None:
                return

            await aiofiles.os.makedirs(self.filepath.parent, exist_ok=True)
            event_loop = get_running_loop()
            await event_loop.run_in_executor(
                None,
                functools.partial(_apply_candle_migrations, self.filepath),
            )

            connection = await aiosqlite.connect(
                self.filepath,
                timeout=SQLITE_TIMEOUT,
            )
            await _configure_connection(connection)
            deleted_count = await _delete_invalid_rows(connection)
            if deleted_count > 0:
                logger.warning(
                    "Deleted %d invalid candle rows from %s",
                    deleted_count,
                    self.filepath,
                )
            self._connection = connection

    async def _close(self) -> None:
        """Close this symbol's persistent write connection."""
        async with self._access_lock:
            connection = self._connection
            if connection is None:
                return
            await connection.close()
            self._connection = None

    async def upsert(self, row: CandleRow) -> None:
        """Insert or replace one complete candle row."""
        if not _is_valid_candle_row(row):
            logger.warning(
                "Skipped invalid candle row for %s %d: %s",
                self.key.symbol,
                self.key.year,
                row,
            )
            return

        async with self._access_lock:
            connection = self._require_connection()
            await connection.execute(
                UPSERT_CANDLE_SQL,
                row,
            )
            await connection.commit()

    async def upsert_many(self, rows: Iterable[CandleRow]) -> None:
        """Insert or replace multiple complete candle rows in one transaction."""
        row_list = list(rows)
        valid_rows = [row for row in row_list if _is_valid_candle_row(row)]
        invalid_count = len(row_list) - len(valid_rows)
        if invalid_count > 0:
            logger.warning(
                "Skipped %d invalid candle rows for %s %d",
                invalid_count,
                self.key.symbol,
                self.key.year,
            )
        if len(valid_rows) == 0:
            return

        async with self._access_lock:
            connection = self._require_connection()
            await connection.executemany(
                UPSERT_CANDLE_SQL,
                valid_rows,
            )
            await connection.commit()

    async def get(self, timestamp: int) -> CandleRow | None:
        """Get a candle row by millisecond timestamp."""
        async with self._access_lock:
            connection = self._require_connection()
            async with connection.execute(
                SELECT_CANDLE_SQL,
                (timestamp,),
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return None
        return CandleRow(*row)

    async def get_latest_before(self, timestamp: int) -> CandleRow | None:
        """Get the latest candle row before a millisecond timestamp."""
        async with self._access_lock:
            connection = self._require_connection()
            async with connection.execute(
                SELECT_LATEST_CANDLE_SQL,
                (timestamp,),
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return None
        return CandleRow(*row)

    async def iter_range(
        self,
        start_timestamp: int,
        end_timestamp: int,
    ) -> AsyncIterator[CandleRow]:
        """Iterate rows in timestamp order using a dedicated read connection."""
        async with aiosqlite.connect(
            self.filepath,
            timeout=SQLITE_TIMEOUT,
        ) as connection:
            await _configure_connection(connection)
            async with connection.execute(
                SELECT_CANDLE_RANGE_SQL,
                (start_timestamp, end_timestamp),
            ) as cursor:
                async for row in cursor:
                    yield CandleRow(*row)

    async def count_range(self, start_timestamp: int, end_timestamp: int) -> int:
        """Count complete candle rows inside a timestamp range."""
        async with self._access_lock:
            connection = self._require_connection()
            async with connection.execute(
                COUNT_CANDLE_RANGE_SQL,
                (start_timestamp, end_timestamp),
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return 0
        return int(row[0])

    async def count_all(self) -> int:
        """Count every complete candle row in this symbol database."""
        async with self._access_lock:
            connection = self._require_connection()
            async with connection.execute(
                COUNT_ALL_CANDLES_SQL,
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return 0
        return int(row[0])

    async def get_timestamp_bounds(self) -> TimestampBounds | None:
        """Get the first and last candle timestamps in this symbol database."""
        async with self._access_lock:
            connection = self._require_connection()
            async with connection.execute(
                SELECT_TIMESTAMP_BOUNDS_SQL,
            ) as cursor:
                row = await cursor.fetchone()

        if row is None or row[0] is None or row[1] is None:
            return None
        return TimestampBounds(first=int(row[0]), last=int(row[1]))

    def _require_connection(self) -> AsyncConnection:
        connection = self._connection
        if connection is None:
            msg = f"CandleData for {self.key.symbol} {self.key.year} is not open"
            raise RuntimeError(msg)
        return connection


class CandleDataStore:
    """Window-owned collection of per-symbol, per-year candle stores."""

    def __init__(self, rootpath: Path, target_symbols: list[str]) -> None:
        """Initialize store wrappers without opening files."""
        self.rootpath = rootpath
        self.target_symbols = target_symbols
        self._cache: dict[CandleDataKey, CandleData] = {}
        self._cache_lock = Lock()
        self._cache_stack = AsyncExitStack()
        self._is_open = False

    async def __aenter__(self) -> Self:
        """Enter the candle-data store scope."""
        await self._open()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close cached symbol-year stores."""
        await self._close()

    async def _open(self) -> None:
        """Create the candle root directory."""
        await aiofiles.os.makedirs(self.rootpath, exist_ok=True)
        async with self._cache_lock:
            self._is_open = True

    async def _close(self) -> None:
        """Close cached symbol-year stores."""
        async with self._cache_lock:
            self._cache.clear()
            self._is_open = False
            cache_stack = self._cache_stack
            self._cache_stack = AsyncExitStack()

        await cache_stack.aclose()

    async def upsert(self, symbol: str, row: CandleRow) -> None:
        """Insert or replace one symbol candle row in its UTC year file."""
        candle_data = await self._get_or_open(CandleDataKey(symbol, _year_from(row)))
        await candle_data.upsert(row)

    async def upsert_many(self, symbol: str, rows: Iterable[CandleRow]) -> None:
        """Insert or replace multiple symbol rows grouped by UTC year."""
        rows_by_year: dict[int, list[CandleRow]] = {}
        for row in rows:
            rows_by_year.setdefault(_year_from(row), []).append(row)

        for year, year_rows in rows_by_year.items():
            candle_data = await self._get_or_open(CandleDataKey(symbol, year))
            await candle_data.upsert_many(year_rows)

    async def get(self, symbol: str, timestamp: int) -> CandleRow | None:
        """Get a symbol candle row by millisecond timestamp."""
        candle_data = await self._get_existing(CandleDataKey(symbol, _year(timestamp)))
        if candle_data is None:
            return None
        return await candle_data.get(timestamp)

    async def get_latest_before(
        self,
        symbol: str,
        timestamp: int,
    ) -> CandleRow | None:
        """Get the latest symbol candle row before a millisecond timestamp."""
        timestamp_year = _year(timestamp)
        years = [
            year for year in await self.list_years(symbol) if year <= timestamp_year
        ]
        for year in reversed(years):
            candle_data = await self._get_existing(CandleDataKey(symbol, year))
            if candle_data is None:
                continue
            row = await candle_data.get_latest_before(timestamp)
            if row is not None:
                return row
        return None

    async def iter_range(
        self,
        symbol: str,
        start_timestamp: int,
        end_timestamp: int,
    ) -> AsyncIterator[CandleRow]:
        """Iterate symbol rows across all touched UTC year files."""
        for year in _iter_years(start_timestamp, end_timestamp):
            candle_data = await self._get_existing(CandleDataKey(symbol, year))
            if candle_data is None:
                continue
            year_start = max(start_timestamp, _year_start_timestamp(year))
            year_end = min(end_timestamp, _year_end_timestamp(year))
            async for row in candle_data.iter_range(year_start, year_end):
                yield row

    async def count_range(
        self,
        symbol: str,
        start_timestamp: int,
        end_timestamp: int,
    ) -> int:
        """Count complete symbol candle rows across touched UTC year files."""
        total = 0
        for year in _iter_years(start_timestamp, end_timestamp):
            candle_data = await self._get_existing(CandleDataKey(symbol, year))
            if candle_data is None:
                continue
            year_start = max(start_timestamp, _year_start_timestamp(year))
            year_end = min(end_timestamp, _year_end_timestamp(year))
            total += await candle_data.count_range(year_start, year_end)
        return total

    async def count_all(self, symbol: str) -> int:
        """Count all complete candle rows for one symbol."""
        total = 0
        for year in await self.list_years(symbol):
            candle_data = await self._get_existing(CandleDataKey(symbol, year))
            if candle_data is not None:
                total += await candle_data.count_all()
        return total

    async def get_timestamp_bounds(self, symbol: str) -> TimestampBounds | None:
        """Get the first and last stored timestamps for one symbol."""
        bounds: list[TimestampBounds] = []
        for year in await self.list_years(symbol):
            candle_data = await self._get_existing(CandleDataKey(symbol, year))
            if candle_data is None:
                continue
            timestamp_bounds = await candle_data.get_timestamp_bounds()
            if timestamp_bounds is not None:
                bounds.append(timestamp_bounds)

        if len(bounds) == 0:
            return None
        return TimestampBounds(
            first=min(bound.first for bound in bounds),
            last=max(bound.last for bound in bounds),
        )

    async def list_years(self, symbol: str) -> list[int]:
        """List UTC years that have stored rows for one symbol."""
        async with self._cache_lock:
            self._raise_if_closed()
            years = {
                key.year for key in self._cache if key.symbol == symbol
            }

        if self.rootpath.exists():
            for year_path in self.rootpath.iterdir():
                if not year_path.is_dir():
                    continue
                try:
                    year = int(year_path.name)
                except ValueError:
                    continue
                if (year_path / f"{symbol}.sqlite").exists():
                    years.add(year)

        nonempty_years: list[int] = []
        for year in sorted(years):
            candle_data = await self._get_existing(CandleDataKey(symbol, year))
            if candle_data is not None and await candle_data.count_all() > 0:
                nonempty_years.append(year)
        return nonempty_years

    async def _get_or_open(self, key: CandleDataKey) -> CandleData:
        async with self._cache_lock:
            self._raise_if_closed()
            candle_data = self._cache.get(key)
            if candle_data is None:
                candle_data = CandleData(key, self._filepath(key))
                await self._cache_stack.enter_async_context(candle_data)
                self._cache[key] = candle_data
            return candle_data

    async def _get_existing(self, key: CandleDataKey) -> CandleData | None:
        async with self._cache_lock:
            self._raise_if_closed()
            candle_data = self._cache.get(key)
            if candle_data is not None:
                return candle_data
            filepath = self._filepath(key)
            if not filepath.exists():
                return None
            candle_data = CandleData(key, filepath)
            await self._cache_stack.enter_async_context(candle_data)
            self._cache[key] = candle_data
            return candle_data

    def _filepath(self, key: CandleDataKey) -> Path:
        return self.rootpath / str(key.year) / f"{key.symbol}.sqlite"

    def _raise_if_closed(self) -> None:
        if not self._is_open:
            msg = "CandleDataStore is closed"
            raise RuntimeError(msg)


def write_candle_rows(rootpath: Path, symbol: str, rows: Iterable[CandleRow]) -> int:
    """Write complete candle rows without retaining them in memory."""
    connections: dict[int, Connection] = {}
    written_count = 0

    def get_connection(year: int, resources: ExitStack) -> Connection:
        connection = connections.get(year)
        if connection is not None:
            return connection

        filepath = rootpath / str(year) / f"{symbol}.sqlite"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        _apply_candle_migrations(filepath)
        connection = sqlite3.connect(filepath, timeout=SQLITE_TIMEOUT)
        resources.callback(connection.close)
        _configure_sync_connection(connection)
        deleted_count = _delete_invalid_rows_sync(connection)
        if deleted_count > 0:
            logger.warning(
                "Deleted %d invalid candle rows from %s",
                deleted_count,
                filepath,
            )
        connections[year] = connection
        return connection

    with ExitStack() as resources:
        try:
            for row in rows:
                if not _is_valid_candle_row(row):
                    logger.warning(
                        "Skipped invalid downloaded candle row for %s: %s",
                        symbol,
                        row,
                    )
                    continue
                connection = get_connection(_year_from(row), resources)
                connection.execute(UPSERT_CANDLE_SQL, row)
                written_count += 1
        except BaseException:
            for connection in connections.values():
                connection.rollback()
            raise

        for connection in connections.values():
            connection.commit()
        return written_count


async def _configure_connection(connection: AsyncConnection) -> None:
    for pragma in SQLITE_WRITE_PRAGMAS:
        await connection.execute(pragma)
    await connection.commit()


def _configure_sync_connection(connection: Connection) -> None:
    for pragma in SQLITE_WRITE_PRAGMAS:
        connection.execute(pragma)
    connection.commit()


async def _delete_invalid_rows(connection: AsyncConnection) -> int:
    cursor = await connection.execute(
        DELETE_INVALID_CANDLES_SQL,
    )
    deleted_count = max(cursor.rowcount, 0)
    await cursor.close()
    await connection.commit()
    return deleted_count


def _delete_invalid_rows_sync(connection: Connection) -> int:
    cursor = connection.execute(
        DELETE_INVALID_CANDLES_SQL,
    )
    deleted_count = max(cursor.rowcount, 0)
    cursor.close()
    connection.commit()
    return deleted_count


def _apply_candle_migrations(filepath: Path) -> None:
    try:
        _apply_candle_migrations_once(filepath)
    except LockTimeout:
        if not _break_stale_yoyo_lock(filepath):
            raise
        _apply_candle_migrations_once(filepath)


def _apply_candle_migrations_once(filepath: Path) -> None:
    migration_path = PACKAGE_PATH / "migrations" / "candle"
    backend_uri = _create_sqlite_backend_uri(filepath)
    with yoyo.get_backend(backend_uri) as backend:
        migrations = yoyo.read_migrations(str(migration_path))
        with backend.lock(timeout=2):
            backend.apply_migrations(backend.to_apply(migrations))


def _break_stale_yoyo_lock(filepath: Path) -> bool:
    with ExitStack() as resources:
        connection = sqlite3.connect(filepath, timeout=SQLITE_TIMEOUT)
        resources.callback(connection.close)
        try:
            cursor = connection.execute("SELECT pid FROM yoyo_lock LIMIT 1")
            resources.callback(cursor.close)
            row = cursor.fetchone()
        except OperationalError:
            return False

        if row is None:
            return False

        locked_pid = int(row[0])
        if _is_process_running(locked_pid):
            return False

        connection.execute("DELETE FROM yoyo_lock")
        connection.commit()
        logger.warning(
            "Broke stale candle migration lock from process %d in %s",
            locked_pid,
            filepath,
        )
        return True


def _is_process_running(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _create_sqlite_backend_uri(filepath: Path) -> str:
    return f"sqlite:///{filepath.resolve().as_posix()}"


def _year(timestamp: int) -> int:
    return datetime.fromtimestamp(timestamp / 1000, tz=UTC).year


def _year_from(row: CandleRow) -> int:
    return _year(row.timestamp)


def _iter_years(start_timestamp: int, end_timestamp: int) -> range:
    return range(_year(start_timestamp), _year(end_timestamp) + 1)


def _year_start_timestamp(year: int) -> int:
    return int(datetime(year, 1, 1, tzinfo=UTC).timestamp() * 1000)


def _year_end_timestamp(year: int) -> int:
    return int(datetime(year + 1, 1, 1, tzinfo=UTC).timestamp() * 1000) - 1


def _is_valid_candle_row(row: CandleRow) -> bool:
    price_values = (row.open, row.high, row.low, row.close)
    if any(not math.isfinite(value) or value <= 0 for value in price_values):
        return False
    if not math.isfinite(row.volume) or row.volume < 0:
        return False
    if row.high < row.low:
        return False
    if row.open < row.low or row.open > row.high:
        return False
    return not (row.close < row.low or row.close > row.high)
