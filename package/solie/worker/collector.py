"""Market data collection worker."""

import math
import random
import webbrowser
from asyncio import Lock, gather, sleep
from collections import deque
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from logging import getLogger
from pathlib import Path
from types import TracebackType
from typing import Any, NamedTuple, Self

import aiofiles.os
import aioshutil
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from polars import DataFrame
from PySide6.QtWidgets import QMenu

from solie.common import UniqueTask, outsource, spawn, spawn_blocking
from solie.logic import (
    DownloadPreset,
    DownloadUnitSize,
    download_aggtrade_csv,
    process_aggtrade_csv,
)
from solie.overlay import (
    DonationGuide,
    DownloadFillOption,
    DownloadFillOptionChooser,
    DownloadYearRange,
)
from solie.utility import (
    MAX_REQUEST_RETRIES,
    PROGRESS_BAR_MAX,
    AggregateTrade,
    ApiRequester,
    ApiStreamer,
    BookTicker,
    CandleRow,
    Cell,
    DurationRecorder,
    MarkPrice,
    TimestampBounds,
    combine_candle_data,
    create_empty_candle_data,
    create_symbol_candle_frame_schema,
    slice_deque,
    to_moment,
)
from solie.widget import overlay
from solie.window import Window

from .united import Team

logger = getLogger(__name__)


class SavedCandleData(NamedTuple):
    """Saved candle data with the symbols that have rows."""

    symbols: list[str]
    data: DataFrame


class Collector:
    """Worker for collecting market data from Binance."""

    def __init__(
        self,
        window: Window,
        scheduler: AsyncIOScheduler,
        team: Team,
    ) -> None:
        """Initialize market data collector."""
        self._window = window
        self._scheduler = scheduler
        self._team = team
        self._workerpath = window.datapath / "collector"

        self._price_precisions: dict[str, int] = {}  # Symbol and decimal places
        self._markets_gone = set[str]()  # Symbols

        self._live_resources = AsyncExitStack()
        self._download_fill_task = UniqueTask()

        self._api_requester = ApiRequester(window.api_rate_store)

        self.aggtrade_candle_sizes: dict[str, int] = {}
        for symbol in window.data_settings.target_symbols:
            self.aggtrade_candle_sizes[symbol] = 0
        self._last_candle_write_summary = "not tried yet"

        # Realtime data
        self.realtime_data = deque[BookTicker | MarkPrice]([], 2 ** (10 + 10 + 2))
        self.aggregate_trades = deque[AggregateTrade]([], 2 ** (10 + 10))

        self._scheduler.add_job(
            self._display_status_information,
            trigger="cron",
            second="*",
        )
        self._scheduler.add_job(
            self._fill_candle_data_holes,
            trigger="cron",
            second="*/10",
        )
        self._scheduler.add_job(
            self._add_candle_data,
            trigger="cron",
            second="*/10",
        )
        self._scheduler.add_job(
            self.get_exchange_information,
            trigger="cron",
            minute="*",
        )

        self._mark_price_streamer = ApiStreamer(
            "wss://fstream.binance.com/ws/!markPrice@arr@1s",
            self._add_mark_price,
        )

        self._book_ticker_streamers = [
            ApiStreamer(
                f"wss://fstream.binance.com/ws/{s.lower()}@bookTicker",
                self._add_book_tickers,
            )
            for s in self._window.data_settings.target_symbols
        ]
        self._aggtrade_streamers = {
            s: ApiStreamer(
                f"wss://fstream.binance.com/ws/{s.lower()}@trade",
                self._add_aggregate_trades,
            )
            for s in self._window.data_settings.target_symbols
        }

        self._connect_ui_events()

    def _connect_ui_events(self) -> None:
        window = self._window

        job = self._guide_donation
        outsource(window.pushButton_9.clicked, job)
        job = self._download_fill_candle_data
        outsource(window.pushButton_2.clicked, job)

        action_menu = QMenu(window)
        window.pushButton_13.setMenu(action_menu)

        text = "Open historical data webpage of Binance"
        job = self._open_binance_data_page
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Stop filling candle data"
        job = self._stop_filling_candle_data
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)

    async def __aenter__(self) -> Self:
        """Enter collector live resources."""
        await aiofiles.os.makedirs(self._workerpath, exist_ok=True)
        await self._live_resources.enter_async_context(self._api_requester)
        streamers = [
            self._mark_price_streamer,
            *self._book_ticker_streamers,
            *self._aggtrade_streamers.values(),
        ]
        for streamer in streamers:
            await self._live_resources.enter_async_context(streamer)
        await self._live_resources.enter_async_context(self._download_fill_task)
        self._live_resources.enter_context(
            self._window.internet_monitor.when_disconnected(
                self._clear_aggregate_trades,
            ),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop collector-owned background work."""
        del exc_type, exc, traceback
        await self._live_resources.aclose()

    async def get_exchange_information(self) -> None:
        """Fetch exchange information from Binance."""
        if not self._window.internet_monitor.connected:
            return

        payload: dict[str, Any] = {}
        response = await self._api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload=payload,
        )
        about_exchange = response

        trading_symbols: set[str] = set()
        for about_symbol in about_exchange["symbols"]:
            symbol = about_symbol["symbol"]
            if about_symbol.get("status") == "TRADING":
                trading_symbols.add(symbol)

            about_filter: dict[str, Any] = {}
            for symbol_filter in about_symbol["filters"]:
                if symbol_filter["filterType"] == "PRICE_FILTER":
                    about_filter = symbol_filter
                    break

            ticksize = float(about_filter["tickSize"])
            price_precision = int(math.log10(1 / ticksize))
            self._price_precisions[symbol] = price_precision
        self._markets_gone = set(self._window.data_settings.target_symbols)
        self._markets_gone.difference_update(trading_symbols)

    async def _fill_candle_data_holes(self) -> None:
        """Fill recent SQLite candle holes by fetching missing aggregate trades."""
        if not self._window.internet_monitor.connected:
            return

        current_moment = to_moment(datetime.now(UTC))
        target_symbols = self._window.data_settings.target_symbols
        needed_moments = int((86400 - 60) / 10) + 1

        full_symbols: set[str] = set()
        request_count = 0
        did_fill = False

        while (
            len(full_symbols) < len(target_symbols)
            and request_count < MAX_REQUEST_RETRIES
        ):
            for symbol in target_symbols:
                if symbol in full_symbols:
                    continue

                filled = await self._fill_symbol_holes(
                    symbol,
                    current_moment,
                    needed_moments,
                )
                if filled is None:
                    full_symbols.add(symbol)
                elif filled:
                    did_fill = True

                request_count += 1
                if request_count >= MAX_REQUEST_RETRIES:
                    break

        if did_fill:
            spawn(self._team.transactor.display_lines())
            spawn(self._team.simulator.display_lines())

    async def _fill_symbol_holes(
        self,
        symbol: str,
        current_moment: datetime,
        needed_moments: int,
    ) -> bool | None:
        """Fill the first detected recent hole for a symbol.

        Returns None when the recent range is complete, True when rows were written,
        and False when the gap could not be filled this pass.
        """
        from_moment = current_moment - timedelta(hours=24)
        until_moment = current_moment - timedelta(minutes=1)
        start_timestamp = int(from_moment.timestamp() * 1000)
        end_timestamp = int(until_moment.timestamp() * 1000)

        missing_timestamp = await self._find_missing_candle_timestamp(
            symbol,
            start_timestamp,
            end_timestamp,
            needed_moments,
        )
        if missing_timestamp is None:
            return None

        aggtrades = await self._fetch_aggtrades_for_gap(symbol, missing_timestamp)
        if aggtrades is None:
            return False

        rows = await self._create_rows_from_gap_aggtrades(
            symbol,
            missing_timestamp,
            aggtrades,
        )
        if len(rows) == 0:
            return False

        await self._window.candle_data_store.upsert_many(symbol, rows)
        return True

    async def _find_missing_candle_timestamp(
        self,
        symbol: str,
        start_timestamp: int,
        end_timestamp: int,
        needed_moments: int,
    ) -> int | None:
        """Find the first missing 10-second candle timestamp for one symbol."""
        written_timestamps = {
            row.timestamp
            async for row in self._window.candle_data_store.iter_range(
                symbol,
                start_timestamp,
                end_timestamp,
            )
        }
        if len(written_timestamps) == needed_moments:
            return None

        for timestamp in range(start_timestamp, end_timestamp + 1, 10_000):
            if timestamp not in written_timestamps:
                return timestamp
        return None

    async def _fetch_aggtrades_for_gap(
        self,
        symbol: str,
        missing_timestamp: int,
    ) -> dict[int, AggregateTrade] | None:
        """Fetch aggregate trades until at least one missing candle can be rebuilt."""
        aggtrades: dict[int, AggregateTrade] = {}
        request_start = missing_timestamp
        fetch_until = missing_timestamp + 10_000

        while request_start < fetch_until:
            payload: dict[str, Any] = {
                "symbol": symbol,
                "startTime": request_start,
                "endTime": fetch_until - 1,
                "limit": 1000,
            }
            response = await self._api_requester.binance(
                http_method="GET",
                path="/fapi/v1/aggTrades",
                payload=payload,
            )

            if len(response) == 0:
                break

            latest_timestamp = request_start - 1
            for about_aggtrade in response:
                aggtrade_id = int(about_aggtrade["a"])
                trade_timestamp = int(about_aggtrade["T"])
                aggtrades[aggtrade_id] = AggregateTrade(
                    timestamp=trade_timestamp,
                    symbol=symbol,
                    price=float(about_aggtrade["p"]),
                    volume=float(about_aggtrade["q"]),
                )
                latest_timestamp = max(latest_timestamp, trade_timestamp)

            if latest_timestamp < request_start:
                break
            request_start = latest_timestamp + 1

        return aggtrades

    async def _create_rows_from_gap_aggtrades(
        self,
        symbol: str,
        missing_timestamp: int,
        aggtrades: dict[int, AggregateTrade],
    ) -> list[CandleRow]:
        """Create complete candle rows from fetched gap trades."""
        sorted_trades = sorted(aggtrades.values(), key=lambda trade: trade.timestamp)
        if len(sorted_trades) > 0:
            last_fetched_timestamp = sorted_trades[-1].timestamp
            last_fetched_moment = to_moment(
                datetime.fromtimestamp(last_fetched_timestamp / 1000, tz=UTC),
            )
            fill_end_moment = last_fetched_moment + timedelta(seconds=10)
            fill_end_timestamp = int(fill_end_moment.timestamp() * 1000)
        else:
            fill_end_timestamp = missing_timestamp + 10_000

        latest_row = await self._window.candle_data_store.get_latest_before(
            symbol,
            missing_timestamp,
        )
        last_price = latest_row.close if latest_row is not None else None

        rows: list[CandleRow] = []
        for timestamp in range(missing_timestamp, fill_end_timestamp, 10_000):
            next_timestamp = timestamp + 10_000
            candle_trades = [
                trade
                for trade in sorted_trades
                if timestamp <= trade.timestamp < next_timestamp
            ]

            if len(candle_trades) > 0:
                prices = [trade.price for trade in candle_trades]
                open_price = prices[0]
                high_price = max(prices)
                low_price = min(prices)
                close_price = prices[-1]
                sum_volume = sum(trade.volume for trade in candle_trades)
            else:
                if last_price is None:
                    continue
                open_price = last_price
                high_price = last_price
                low_price = last_price
                close_price = last_price
                sum_volume = 0.0

            rows.append(
                CandleRow(
                    timestamp=timestamp,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=sum_volume,
                ),
            )
            last_price = close_price

        return rows

    async def _has_candle_data(self) -> bool:
        """Return whether any symbol store has candle rows."""
        for symbol in self._window.data_settings.target_symbols:
            if await self._window.candle_data_store.count_all(symbol) > 0:
                return True
        return False

    async def _display_status_information(self) -> None:
        if not await self._has_candle_data():
            return

        if len(self._price_precisions) == 0:
            return

        self._update_price_labels()
        self._window.label_6.setText(await self._create_status_text())

    def _update_price_labels(self) -> None:
        """Update latest price labels for each target symbol."""
        price_precisions = self._price_precisions
        recent_aggregate_trades = slice_deque(self.aggregate_trades, 2 ** (10 + 6))
        for symbol in self._window.data_settings.target_symbols:
            latest_price: float | None = None
            for aggregate_trade in reversed(recent_aggregate_trades):
                if aggregate_trade.symbol == symbol:
                    latest_price = aggregate_trade.price
                    break
            if latest_price is None:
                text = "Unavailable"
            else:
                price_precision = price_precisions[symbol]
                text = f"${latest_price:.{price_precision}f}"
            self._window.price_labels[symbol].setText(text)

    async def _create_status_text(self) -> str:
        """Create the collector status text shown in the Collect tab."""
        if len(self._markets_gone) == 0:
            return await self._create_normal_status_text()

        markets_gone = sorted(self._markets_gone)
        return (
            f"It seems that {', '.join(markets_gone)} markets are "
            "removed by Binance. You should make a new data folder."
        )

    async def _create_normal_status_text(self) -> str:
        """Create the normal collector status text."""
        cumulation_rate = await self.check_candle_data_cumulation_rate()
        written_seconds = await self._get_written_candle_seconds()
        written_length = timedelta(seconds=written_seconds)
        range_days = written_length.days
        range_hours, remains = divmod(written_length.seconds, 3600)
        range_minutes, _ = divmod(remains, 60)
        written_length_text = f"{range_days}d {range_hours}h {range_minutes}m"

        return (
            f"24h candle data accumulation rate {cumulation_rate * 100:.2f}%"
            "  ⦁  "
            f"Realtime data length {written_length_text}"
        )

    async def _get_written_candle_seconds(self) -> float:
        """Return total time span covered by per-symbol candle files."""
        bounds: list[TimestampBounds] = []
        for symbol in self._window.data_settings.target_symbols:
            candle_store = self._window.candle_data_store
            timestamp_bounds = await candle_store.get_timestamp_bounds(symbol)
            if timestamp_bounds is not None:
                bounds.append(timestamp_bounds)

        if len(bounds) == 0:
            return 0.0
        first_written_time = min(bound.first for bound in bounds)
        last_written_time = max(bound.last for bound in bounds)
        return (last_written_time - first_written_time) / 10**3

    async def check_candle_data_cumulation_rate(self) -> float:
        """Calculate percentage of collected candle data."""
        current_moment = to_moment(datetime.now(UTC))
        count_end_moment = current_moment - timedelta(seconds=10)
        count_start_moment = count_end_moment - timedelta(hours=24)

        count_end_moment -= timedelta(seconds=1)

        start_timestamp = int(count_start_moment.timestamp() * 1000)
        end_timestamp = int(count_end_moment.timestamp() * 1000)
        counts = [
            await self._window.candle_data_store.count_range(
                symbol,
                start_timestamp,
                end_timestamp,
            )
            for symbol in self._window.data_settings.target_symbols
        ]
        cumulated = min(counts, default=0)
        needed_moments = 6 * 60 * 24
        return cumulated / needed_moments

    async def wait_for_candle_data_ready(self, before_moment: datetime) -> bool:
        """Wait for candle data to be ready up to the specified moment.

        Returns True when data is ready, False on timeout.
        """
        for _ in range(50):
            timestamp = int(before_moment.timestamp() * 1000)
            stores = self._window.candle_data_store
            rows = [
                await stores.get(symbol, timestamp)
                for symbol in self._window.data_settings.target_symbols
            ]
            if all(row is not None for row in rows):
                return True
            await sleep(0.1)
        return False

    async def _open_binance_data_page(self) -> None:
        await spawn_blocking(
            webbrowser.open,
            "https://www.binance.com/en/landing/data",
        )

    async def _download_fill_candle_data(self) -> None:
        fill_option = await overlay(DownloadFillOptionChooser())
        if fill_option is None:
            return
        unique_task = self._download_fill_task
        unique_task.spawn(
            self._download_fill_candle_data_real(unique_task, fill_option),
        )

    def _create_download_presets(
        self,
        fill_option: DownloadYearRange | DownloadFillOption,
    ) -> list[DownloadPreset]:
        download_presets: list[DownloadPreset] = []
        target_symbols = self._window.data_settings.target_symbols
        match fill_option:
            case DownloadYearRange(start=year_from, end=year_to):
                for year in range(year_from, year_to + 1):
                    for month in range(1, 12 + 1):
                        download_presets.extend(
                            DownloadPreset(
                                symbol=s,
                                unit_size=DownloadUnitSize.MONTHLY,
                                year=year,
                                month=month,
                            )
                            for s in target_symbols
                        )
            case DownloadFillOption.FROM_YEAR_START_TO_LAST_MONTH:
                now = datetime.now(UTC)
                current_year = now.year
                current_month = now.month
                for month in range(1, current_month):
                    download_presets.extend(
                        DownloadPreset(
                            symbol=s,
                            unit_size=DownloadUnitSize.MONTHLY,
                            year=current_year,
                            month=month,
                        )
                        for s in target_symbols
                    )
            case DownloadFillOption.THIS_MONTH:
                now = datetime.now(UTC)
                current_year = now.year
                current_month = now.month
                current_day = now.day
                for target_day in range(1, current_day):
                    download_presets.extend(
                        DownloadPreset(
                            symbol=s,
                            unit_size=DownloadUnitSize.DAILY,
                            year=current_year,
                            month=current_month,
                            day=target_day,
                        )
                        for s in target_symbols
                    )
            case DownloadFillOption.LAST_TWO_DAYS:
                now = datetime.now(UTC)
                yesterday = now - timedelta(hours=24)
                day_before_yesterday = yesterday - timedelta(hours=24)
                download_presets.extend(
                    DownloadPreset(
                        symbol=s,
                        unit_size=DownloadUnitSize.DAILY,
                        year=day_before_yesterday.year,
                        month=day_before_yesterday.month,
                        day=day_before_yesterday.day,
                    )
                    for s in target_symbols
                )
                download_presets.extend(
                    DownloadPreset(
                        symbol=s,
                        unit_size=DownloadUnitSize.DAILY,
                        year=yesterday.year,
                        month=yesterday.month,
                        day=yesterday.day,
                    )
                    for s in target_symbols
                )

        return download_presets

    async def _download_fill_candle_data_real(
        self,
        unique_task: UniqueTask,
        fill_option: DownloadYearRange | DownloadFillOption,
    ) -> None:
        download_presets = self._create_download_presets(fill_option)
        random.shuffle(download_presets)

        total_steps = len(download_presets) * 2
        done_steps = Cell(0)

        async def play_progress_bar() -> None:
            while True:
                if done_steps.value == total_steps:
                    progressbar_value = self._window.progressBar_3.value()
                    if progressbar_value == PROGRESS_BAR_MAX:
                        await sleep(0.1)
                        self._window.progressBar_3.setValue(0)
                        return
                before_value = self._window.progressBar_3.value()
                if before_value < PROGRESS_BAR_MAX:
                    remaining = (
                        math.ceil(1000 / total_steps * done_steps.value) - before_value
                    )
                    new_value = before_value + math.ceil(remaining * 0.2)
                    self._window.progressBar_3.setValue(new_value)
                await sleep(0.01)

        bar_task = spawn(play_progress_bar())
        bar_task.add_done_callback(lambda _: self._window.progressBar_3.setValue(0))
        unique_task.add_done_callback(lambda _: bar_task.cancel())

        current_year = datetime.now(UTC).year
        classified_download_presets = self._classify_presets_by_year(download_presets)

        for preset_year, download_presets in classified_download_presets.items():
            combined_df = await self._download_and_combine_presets(
                preset_year,
                download_presets,
                done_steps,
            )
            if combined_df is not None:
                await self._save_or_merge_downloaded_data(
                    preset_year,
                    current_year,
                    combined_df,
                )

    def _classify_presets_by_year(
        self,
        download_presets: list[DownloadPreset],
    ) -> dict[int, list[DownloadPreset]]:
        """Classify download presets by year."""
        all_years = sorted({t.year for t in download_presets})
        classified_download_presets: dict[int, list[DownloadPreset]] = {
            y: [] for y in all_years
        }
        for download_preset in download_presets:
            classified_download_presets[download_preset.year].append(download_preset)
        return classified_download_presets

    async def _download_and_combine_presets(
        self,
        preset_year: int,
        download_presets: list[DownloadPreset],
        done_steps: Cell[int],
    ) -> DataFrame | None:
        """Download CSV files for presets and combine them."""
        download_dir = self._workerpath / f"downloaded_csv_{preset_year}"
        await aioshutil.rmtree(download_dir, ignore_errors=True)
        await aiofiles.os.makedirs(download_dir, exist_ok=True)

        downloaded_dfs: list[DataFrame] = []

        async def download_fill(
            download_preset: DownloadPreset,
            download_lock: Lock,
            download_dir: Path,
            downloaded_dfs: list[DataFrame],
        ) -> None:
            async with download_lock:
                zip_file_path = await download_aggtrade_csv(
                    download_preset,
                    download_dir,
                )
            done_steps.value += 1

            if zip_file_path is not None:
                downloaded_df = await spawn_blocking(
                    process_aggtrade_csv,
                    download_preset,
                    zip_file_path,
                )
                if downloaded_df is not None:
                    downloaded_dfs.append(downloaded_df)
            done_steps.value += 1

        download_lock = Lock()
        coros = (
            download_fill(p, download_lock, download_dir, downloaded_dfs)
            for p in download_presets
        )
        await gather(*coros)

        await aioshutil.rmtree(download_dir, ignore_errors=True)

        if len(downloaded_dfs) > 0:
            return await spawn_blocking(
                combine_candle_data,
                downloaded_dfs,
            )
        logger.info("No data downloaded for the year %d", preset_year)
        return None

    async def _save_or_merge_downloaded_data(
        self,
        preset_year: int,
        current_year: int,
        combined_df: DataFrame,
    ) -> None:
        """Save downloaded data to disk or merge with current data."""
        if preset_year < current_year:
            await self._write_downloaded_candle_rows(combined_df)
            logger.info("Saved candle data of year %d to SQLite", preset_year)
        else:
            await self._write_downloaded_candle_rows(combined_df)
            logger.info("Filled the candle data with the downloaded history data")

        spawn(self._team.transactor.display_lines())
        spawn(self._team.simulator.display_lines())
        spawn(self._team.simulator.display_available_years())

    async def _write_downloaded_candle_rows(self, combined_df: DataFrame) -> None:
        """Persist downloaded candle rows to SQLite-backed candle stores."""
        rows_by_symbol: dict[str, list[CandleRow]] = {}
        for row in combined_df.iter_rows(named=True):
            symbol = str(row["symbol"])
            candle_row = CandleRow(
                timestamp=int(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            rows_by_symbol.setdefault(symbol, []).append(candle_row)

        for symbol, rows in rows_by_symbol.items():
            await self._window.candle_data_store.upsert_many(symbol, rows)

    async def _add_book_tickers(self, received: dict[str, Any]) -> None:
        with DurationRecorder("ADD_BOOK_TICKERS", self._window.task_durations):
            symbol = received["s"]
            best_bid = float(received["b"])
            best_ask = float(received["a"])
            event_time = received["E"]  # In milliseconds

            book_ticker = BookTicker(
                timestamp=event_time,
                symbol=symbol,
                best_bid_price=best_bid,
                best_ask_price=best_ask,
            )
            self.realtime_data.append(book_ticker)

    async def _add_mark_price(self, received: list[dict[str, Any]]) -> None:
        with DurationRecorder("ADD_MARK_PRICE", self._window.task_durations):
            if len(received) == 0:
                return

            target_symbols = self._window.data_settings.target_symbols
            event_time = received[0]["E"]  # In milliseconds
            for about_mark_price in received:
                symbol = about_mark_price["s"]
                if symbol in target_symbols:
                    mark_price = float(about_mark_price["p"])
                    mark_price = MarkPrice(
                        timestamp=event_time,
                        symbol=symbol,
                        mark_price=mark_price,
                    )
                    self.realtime_data.append(mark_price)

    async def _add_aggregate_trades(self, received: dict[str, Any]) -> None:
        with DurationRecorder("ADD_AGGREGATE_TRADES", self._window.task_durations):
            symbol = received["s"]
            price = float(received["p"])
            volume = float(received["q"])
            trade_time = received["T"]  # In milliseconds

            aggregate_trade = AggregateTrade(
                timestamp=trade_time,
                symbol=symbol,
                price=price,
                volume=volume,
            )
            self.aggregate_trades.append(aggregate_trade)

    async def _clear_aggregate_trades(self) -> None:
        self.aggregate_trades.clear()

    def _is_aggtrade_stream_ready(self, symbol: str, collect_from: int) -> bool:
        """Return whether the symbol trade stream covered the candle window."""
        connected_since = self._aggtrade_streamers[symbol].connected_since
        if connected_since is None:
            return False
        connected_timestamp = int(connected_since.timestamp() * 1000)
        return connected_timestamp <= collect_from

    def _collect_candle_window_trades(
        self,
        collect_from: int,
        collect_to: int,
    ) -> list[AggregateTrade] | None:
        """Collect aggregate trades inside one candle window."""
        aggregate_trades = self.aggregate_trades
        if len(aggregate_trades) == 0:
            return []

        first_received_index = aggregate_trades[0].timestamp
        if collect_from <= first_received_index:
            return None

        collected: list[AggregateTrade] = []
        for aggregate_trade in reversed(aggregate_trades):
            if aggregate_trade.timestamp < collect_from - 1000:
                break
            collected.append(aggregate_trade)

        collected.reverse()
        return [t for t in collected if collect_from <= t.timestamp < collect_to]

    async def _create_realtime_candle_row(
        self,
        symbol: str,
        candle_timestamp: int,
        collect_from: int,
        symbol_aggregate_trades: list[AggregateTrade],
    ) -> CandleRow | None:
        """Create one realtime candle row from trades or confirmed quietness."""
        if len(symbol_aggregate_trades) > 0:
            open_price = symbol_aggregate_trades[0].price
            high_price = max(t.price for t in symbol_aggregate_trades)
            low_price = min(t.price for t in symbol_aggregate_trades)
            close_price = symbol_aggregate_trades[-1].price
            sum_volume = sum(t.volume for t in symbol_aggregate_trades)
        else:
            latest_row = await self._window.candle_data_store.get_latest_before(
                symbol,
                collect_from,
            )
            if latest_row is None:
                return None
            last_price = latest_row.close
            open_price = last_price
            high_price = last_price
            low_price = last_price
            close_price = last_price
            sum_volume = 0.0

        return CandleRow(
            timestamp=candle_timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=sum_volume,
        )

    async def _add_candle_data(self) -> None:
        with DurationRecorder("ADD_CANDLE_DATA", self._window.task_durations):
            if not self._window.internet_monitor.connected:
                self._last_candle_write_summary = "waiting for internet"
                return

            current_moment = to_moment(datetime.now(UTC))
            before_moment = current_moment - timedelta(seconds=10.0)
            collect_from = int(before_moment.timestamp()) * 1000
            collect_to = int(current_moment.timestamp()) * 1000
            collected_aggregate_trades = self._collect_candle_window_trades(
                collect_from,
                collect_to,
            )
            if collected_aggregate_trades is None:
                self._last_candle_write_summary = "waiting for a full 10s window"
                return

            rows: dict[str, CandleRow] = {}
            pending_symbols: set[str] = set()
            for symbol in self._window.data_settings.target_symbols:
                symbol_aggregate_trades = [
                    t for t in collected_aggregate_trades if t.symbol == symbol
                ]
                self.aggtrade_candle_sizes[symbol] = len(symbol_aggregate_trades)

                if not self._is_aggtrade_stream_ready(symbol, collect_from):
                    pending_symbols.add(symbol)
                    continue

                row = await self._create_realtime_candle_row(
                    symbol,
                    int(before_moment.timestamp() * 1000),
                    collect_from,
                    symbol_aggregate_trades,
                )
                if row is not None:
                    rows[symbol] = row

            if len(rows) == 0:
                if len(pending_symbols) > 0:
                    self._last_candle_write_summary = "waiting for trade streams"
                else:
                    self._last_candle_write_summary = "no symbols had writable candles"
                return

            await self._write_candle_rows(rows)
            row_count = len(rows)
            timestamp_text = datetime.fromtimestamp(
                rows[next(iter(rows))].timestamp / 10**3,
                tz=UTC,
            ).strftime("%H:%M:%S")
            self._last_candle_write_summary = (
                f"wrote {row_count} rows at {timestamp_text}"
            )

    async def _write_candle_rows(
        self,
        rows: dict[str, CandleRow],
    ) -> None:
        """Write newly collected candle rows to SQLite storage."""
        for symbol, row in rows.items():
            await self._window.candle_data_store.upsert(symbol, row)

    async def read_symbol_candle_data(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> DataFrame:
        """Read one symbol's candle rows from SQLite into a Polars frame."""
        start_timestamp = int(start.timestamp() * 1000)
        end_timestamp = int(end.timestamp() * 1000)
        rows = [
            row
            async for row in self._window.candle_data_store.iter_range(
                symbol,
                start_timestamp,
                end_timestamp,
            )
        ]
        return DataFrame(
            {
                "timestamp": [row.timestamp for row in rows],
                f"{symbol}/OPEN": [row.open for row in rows],
                f"{symbol}/HIGH": [row.high for row in rows],
                f"{symbol}/LOW": [row.low for row in rows],
                f"{symbol}/CLOSE": [row.close for row in rows],
                f"{symbol}/VOLUME": [row.volume for row in rows],
            },
            schema=create_symbol_candle_frame_schema(symbol),
        )

    async def _stop_filling_candle_data(self) -> None:
        self._download_fill_task.cancel()

    async def _guide_donation(self) -> None:
        await overlay(DonationGuide())

    async def check_saved_years(self) -> list[int]:
        """Get list of years with saved candle data."""
        saved_years: set[int] = set()
        for symbol in self._window.data_settings.target_symbols:
            symbol_years = await self._window.candle_data_store.list_years(symbol)
            saved_years.update(symbol_years)
        if len(saved_years) == 0:
            return [datetime.now(UTC).year]
        return sorted(saved_years)

    async def read_saved_candle_data(self, year: int) -> DataFrame:
        """Read saved candle data for specific year."""
        return await self.read_saved_symbols_candle_data(
            year,
            self._window.data_settings.target_symbols,
        )

    async def read_available_saved_candle_data(
        self,
        year: int,
        symbols: list[str],
    ) -> SavedCandleData:
        """Read saved candle data and report symbols with stored rows."""
        year_start = datetime(year, 1, 1, tzinfo=UTC)
        year_end = datetime(year + 1, 1, 1, tzinfo=UTC) - timedelta(milliseconds=1)

        available_symbols: list[str] = []
        candle_frames: list[DataFrame] = []
        for symbol in symbols:
            candle_frame = await self.read_symbol_candle_data(
                symbol,
                year_start,
                year_end,
            )
            if len(candle_frame) == 0:
                continue
            available_symbols.append(symbol)
            candle_frames.append(candle_frame)

        if len(candle_frames) == 0:
            return SavedCandleData(
                symbols=[],
                data=create_empty_candle_data([]),
            )

        combined_frame = candle_frames[0]
        for candle_frame in candle_frames[1:]:
            combined_frame = combined_frame.join(
                candle_frame,
                on="timestamp",
                how="inner",
            )
        return SavedCandleData(symbols=available_symbols, data=combined_frame)

    async def read_saved_symbols_candle_data(
        self,
        year: int,
        symbols: list[str],
    ) -> DataFrame:
        """Read saved candle data for specific symbols in a year."""
        saved_data = await self.read_available_saved_candle_data(year, symbols)
        return saved_data.data
