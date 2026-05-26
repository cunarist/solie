"""SQLite-backed candle data storage."""

from asyncio import to_thread
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple, Self

import aiofiles.os
import aiosqlite
from yoyo import get_backend, read_migrations

from solie.common import PACKAGE_PATH


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
        self._connection: aiosqlite.Connection | None = None

    async def __aenter__(self) -> Self:
        """Open the database for context-manager use."""
        await self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close the database for context-manager use."""
        await self.close()

    async def open(self) -> None:
        """Open this symbol's database and apply migrations."""
        if self._connection is not None:
            return

        await aiofiles.os.makedirs(self.filepath.parent, exist_ok=True)
        await to_thread(_apply_candle_migrations, self.filepath)

        connection = await aiosqlite.connect(self.filepath)
        await _configure_connection(connection)
        self._connection = connection

    async def close(self) -> None:
        """Close this symbol's persistent write connection."""
        connection = self._connection
        if connection is None:
            return
        self._connection = None
        await connection.close()

    async def upsert(self, row: CandleRow) -> None:
        """Insert or replace one complete candle row."""
        connection = self._require_connection()
        await connection.execute(
            """
            INSERT INTO candles(timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(timestamp) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume
            """,
            row,
        )
        await connection.commit()

    async def upsert_many(self, rows: Iterable[CandleRow]) -> None:
        """Insert or replace multiple complete candle rows in one transaction."""
        connection = self._require_connection()
        await connection.executemany(
            """
            INSERT INTO candles(timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(timestamp) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume
            """,
            rows,
        )
        await connection.commit()

    async def get(self, timestamp: int) -> CandleRow | None:
        """Get a candle row by millisecond timestamp."""
        connection = self._require_connection()
        async with connection.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE timestamp = ?
            """,
            (timestamp,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return CandleRow(*row)

    async def get_latest_before(self, timestamp: int) -> CandleRow | None:
        """Get the latest candle row before a millisecond timestamp."""
        connection = self._require_connection()
        async with connection.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE timestamp < ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
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
        async with aiosqlite.connect(self.filepath) as connection:
            await _configure_connection(connection)
            async with connection.execute(
                """
                SELECT timestamp, open, high, low, close, volume
                FROM candles
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp
                """,
                (start_timestamp, end_timestamp),
            ) as cursor:
                async for row in cursor:
                    yield CandleRow(*row)

    async def count_range(self, start_timestamp: int, end_timestamp: int) -> int:
        """Count complete candle rows inside a timestamp range."""
        connection = self._require_connection()
        async with connection.execute(
            """
            SELECT COUNT(*)
            FROM candles
            WHERE timestamp >= ? AND timestamp <= ?
            """,
            (start_timestamp, end_timestamp),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return 0
        return int(row[0])

    async def count_all(self) -> int:
        """Count every complete candle row in this symbol database."""
        connection = self._require_connection()
        async with connection.execute("SELECT COUNT(*) FROM candles") as cursor:
            row = await cursor.fetchone()

        if row is None:
            return 0
        return int(row[0])

    async def get_timestamp_bounds(self) -> TimestampBounds | None:
        """Get the first and last candle timestamps in this symbol database."""
        connection = self._require_connection()
        async with connection.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM candles",
        ) as cursor:
            row = await cursor.fetchone()

        if row is None or row[0] is None or row[1] is None:
            return None
        return TimestampBounds(first=int(row[0]), last=int(row[1]))

    def _require_connection(self) -> aiosqlite.Connection:
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

    async def open(self) -> None:
        """Create the candle root directory."""
        await aiofiles.os.makedirs(self.rootpath, exist_ok=True)

    async def close(self) -> None:
        """Close cached symbol-year stores."""
        for candle_data in self._cache.values():
            await candle_data.close()

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
        candle_data = self._cache.get(key)
        if candle_data is None:
            candle_data = CandleData(key, self._filepath(key))
            await candle_data.open()
            self._cache[key] = candle_data
        return candle_data

    async def _get_existing(self, key: CandleDataKey) -> CandleData | None:
        if key in self._cache:
            return self._cache[key]
        filepath = self._filepath(key)
        if not filepath.exists():
            return None
        candle_data = CandleData(key, filepath)
        await candle_data.open()
        self._cache[key] = candle_data
        return candle_data

    def _filepath(self, key: CandleDataKey) -> Path:
        return self.rootpath / str(key.year) / f"{key.symbol}.sqlite"


async def _configure_connection(connection: aiosqlite.Connection) -> None:
    await connection.execute("PRAGMA journal_mode = WAL")
    await connection.execute("PRAGMA synchronous = NORMAL")
    await connection.execute("PRAGMA foreign_keys = ON")
    await connection.execute("PRAGMA busy_timeout = 5000")
    await connection.commit()


def _apply_candle_migrations(filepath: Path) -> None:
    migration_path = PACKAGE_PATH / "migrations" / "candle"
    backend_uri = _create_sqlite_backend_uri(filepath)
    with get_backend(backend_uri) as backend:
        migrations = read_migrations(str(migration_path))
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))


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
