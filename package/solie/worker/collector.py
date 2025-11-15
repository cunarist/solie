import math
import random
import webbrowser
from asyncio import sleep, wait
from collections import deque
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any

import aiofiles.os
import numpy as np
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6.QtWidgets import QMenu

from solie.common import UniqueTask, outsource, spawn, spawn_blocking
from solie.overlay import DonationGuide, DownloadFillOption
from solie.utility import (
    AggregateTrade,
    ApiRequester,
    ApiStreamer,
    BookTicker,
    DownloadPreset,
    DownloadUnitSize,
    DurationRecorder,
    MarkPrice,
    RWLock,
    combine_candle_data,
    create_empty_candle_data,
    download_aggtrade_data,
    fill_holes_with_aggtrades,
    format_numeric,
    internet_connected,
    slice_deque,
    sort_data_frame,
    to_moment,
    when_internet_disconnected,
)
from solie.widget import overlay
from solie.window import Window

from .united import team

logger = getLogger(__name__)


class Collector:
    def __init__(self, window: Window, scheduler: AsyncIOScheduler):
        # ■■■■■ for data management ■■■■■

        self.window = window
        self.scheduler = scheduler
        self.workerpath = window.datapath / "collector"

        # ■■■■■ internal memory ■■■■■

        self.price_precisions: dict[str, int] = {}  # Symbol and decimal places
        self.markets_gone = set[str]()  # Symbols

        self.download_fill_task = UniqueTask()

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.aggtrade_candle_sizes: dict[str, int] = {}
        for symbol in window.data_settings.target_symbols:
            self.aggtrade_candle_sizes[symbol] = 0

        # Candle data.
        # It's expected to have only the data of current year,
        # while data of previous years are stored in the disk.
        self.candle_data = RWLock(
            create_empty_candle_data(window.data_settings.target_symbols)
        )

        # Realtime data
        self.realtime_data = deque[BookTicker | MarkPrice]([], 2 ** (10 + 10 + 2))
        self.aggregate_trades = deque[AggregateTrade]([], 2 ** (10 + 10))

        # ■■■■■ repetitive schedules ■■■■■

        self.scheduler.add_job(
            self.display_status_information,
            trigger="cron",
            second="*",
        )
        self.scheduler.add_job(
            self.fill_candle_data_holes,
            trigger="cron",
            second="*/10",
        )
        self.scheduler.add_job(
            self.add_candle_data,
            trigger="cron",
            second="*/10",
        )
        self.scheduler.add_job(
            self.organize_data,
            trigger="cron",
            minute="*",
        )
        self.scheduler.add_job(
            self.get_exchange_information,
            trigger="cron",
            minute="*",
        )
        self.scheduler.add_job(
            self._save_candle_data,
            trigger="cron",
            hour="*",
        )

        # ■■■■■ websocket streamings ■■■■■

        self.mark_price_streamer = ApiStreamer(
            "wss://fstream.binance.com/ws/!markPrice@arr@1s",
            self.add_mark_price,
        )

        self.book_ticker_streamers = [
            ApiStreamer(
                f"wss://fstream.binance.com/ws/{s.lower()}@bookTicker",
                self.add_book_tickers,
            )
            for s in self.window.data_settings.target_symbols
        ]
        self.aggtrade_streamers = [
            ApiStreamer(
                f"wss://fstream.binance.com/ws/{s.lower()}@aggTrade",
                self.add_aggregate_trades,
            )
            for s in self.window.data_settings.target_symbols
        ]

        # ■■■■■ invoked by the internet connection status change ■■■■■

        when_internet_disconnected(self.clear_aggregate_trades)

        # ■■■■■ connect UI events ■■■■■

        job = self.guide_donation
        outsource(window.pushButton_9.clicked, job)
        job = self.download_fill_candle_data
        outsource(window.pushButton_2.clicked, job)

        action_menu = QMenu(self.window)
        self.window.pushButton_13.setMenu(action_menu)

        text = "Open historical data webpage of Binance"
        job = self.open_binance_data_page
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Stop filling candle data"
        job = self.stop_filling_candle_data
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)

    async def load_work(self):
        await aiofiles.os.makedirs(self.workerpath, exist_ok=True)

        # candle data
        current_year = datetime.now(timezone.utc).year
        async with self.candle_data.write_lock as cell:
            filepath = self.workerpath / f"candle_data_{current_year}.pickle"
            if await aiofiles.os.path.isfile(filepath):
                df: pd.DataFrame = await spawn_blocking(pd.read_pickle, filepath)
                if not df.index.is_monotonic_increasing:
                    df = await spawn_blocking(sort_data_frame, df)
                cell.data = df

    async def dump_work(self):
        await self._save_candle_data()

    async def organize_data(self):
        duration_recorder = DurationRecorder("ORGANIZE_COLLECTOR_DATA")

        async with self.candle_data.write_lock as cell:
            original_index = cell.data.index
            if not cell.data.index.is_unique:
                unique_index = original_index.drop_duplicates()
                cell.data = cell.data.reindex(unique_index)
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await spawn_blocking(sort_data_frame, cell.data)

        duration_recorder.record()

    async def _save_candle_data(self):
        # ■■■■■ default values ■■■■■

        current_year = datetime.now(timezone.utc).year
        filepath = self.workerpath / f"candle_data_{current_year}.pickle"
        filepath_new = self.workerpath / f"candle_data_{current_year}.pickle.new"
        filepath_backup = self.workerpath / f"candle_data_{current_year}.pickle.backup"

        async with self.candle_data.read_lock as cell:
            mask = cell.data.index.year == current_year  # type:ignore
            year_df: pd.DataFrame = cell.data[mask].copy()

        # ■■■■■ make a new file ■■■■■

        await spawn_blocking(year_df.to_pickle, filepath_new)

        # ■■■■■ safely replace the existing file ■■■■■

        if await aiofiles.os.path.isfile(filepath_backup):
            await aiofiles.os.remove(filepath_backup)
        if await aiofiles.os.path.isfile(filepath):
            await aiofiles.os.rename(filepath, filepath_backup)
        if await aiofiles.os.path.isfile(filepath_new):
            await aiofiles.os.rename(filepath_new, filepath)

    async def get_exchange_information(self):
        if not internet_connected():
            return

        payload: dict[str, Any] = {}
        response = await self.api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload=payload,
        )
        about_exchange = response

        for about_symbol in about_exchange["symbols"]:
            symbol = about_symbol["symbol"]

            about_filter: dict[str, Any] = {}
            for filter in about_symbol["filters"]:
                if filter["filterType"] == "PRICE_FILTER":
                    about_filter = filter
                    break

            ticksize = float(about_filter["tickSize"])
            price_precision = int(math.log10(1 / ticksize))
            self.price_precisions[symbol] = price_precision

    async def fill_candle_data_holes(self):
        # ■■■■■ check internet connection ■■■■■

        if not internet_connected():
            return

        # ■■■■■ moments ■■■■■

        current_moment = to_moment(datetime.now(timezone.utc))
        split_moment = current_moment - timedelta(days=2)

        # ■■■■■ fill holes ■■■■■

        full_symbols = set[str]()
        request_count = 0

        # only the recent part
        async with self.candle_data.read_lock as cell:
            recent_candle_data = cell.data[cell.data.index >= split_moment].copy()

        did_fill = False

        target_symbols = self.window.data_settings.target_symbols
        needed_moments = int((86400 - 60) / 10) + 1
        while len(full_symbols) < len(target_symbols) and request_count < 10:
            for symbol in target_symbols:
                if symbol in full_symbols:
                    continue

                from_moment = current_moment - timedelta(hours=24)
                until_moment = current_moment - timedelta(minutes=1)

                columns = [str(s) for s in recent_candle_data.columns]
                chosen_columns = [s for s in columns if s.startswith(symbol)]
                inspect_df: pd.DataFrame = recent_candle_data[chosen_columns][
                    from_moment:until_moment
                ]
                base_index = inspect_df.dropna().index
                temp_sr = pd.Series(0, index=base_index)
                written_moments = len(temp_sr)

                if written_moments == needed_moments:
                    # case when there are no holes
                    full_symbols.add(symbol)
                    continue

                if from_moment not in temp_sr.index:
                    temp_sr[from_moment] = np.nan
                if until_moment not in temp_sr.index:
                    temp_sr[until_moment] = np.nan
                temp_sr = await spawn_blocking(temp_sr.asfreq, "10s")
                isnan_sr = await spawn_blocking(temp_sr.isna)
                nan_index = isnan_sr[isnan_sr == 1].index
                moment_to_fill_from: datetime = nan_index[0]

                # request historical aggtrade data
                aggtrades: dict[int, AggregateTrade] = {}
                last_fetched_time = moment_to_fill_from
                while last_fetched_time < moment_to_fill_from + timedelta(seconds=10):
                    # intend to fill at least one 10 second candle bar
                    payload = {
                        "symbol": symbol,
                        "startTime": int(last_fetched_time.timestamp() * 1000),
                        "limit": 1000,
                    }
                    response = await self.api_requester.binance(
                        http_method="GET",
                        path="/fapi/v1/aggTrades",
                        payload=payload,
                    )
                    request_count += 1
                    if len(response) == 0:
                        self.markets_gone.add(symbol)
                        break
                    for about_aggtrade in response:
                        aggtrade_id = int(about_aggtrade["a"])
                        aggtrade = AggregateTrade(
                            timestamp=about_aggtrade["T"],
                            symbol=symbol,
                            price=float(about_aggtrade["p"]),
                            volume=float(about_aggtrade["q"]),
                        )
                        aggtrades[aggtrade_id] = aggtrade
                    last_fetched_id = max(aggtrades.keys())
                    last_fetched_time = datetime.fromtimestamp(
                        aggtrades[last_fetched_id].timestamp / 1000, tz=timezone.utc
                    )

                recent_candle_data = await spawn_blocking(
                    fill_holes_with_aggtrades,
                    symbol,
                    recent_candle_data,
                    aggtrades,
                    moment_to_fill_from,
                    last_fetched_time,
                )
                did_fill = True

        if not did_fill:
            return

        # combine
        async with self.candle_data.write_lock as cell:
            original_candle_data = cell.data[cell.data.index < split_moment]
            # in case the other data is added during the task
            # read the data again
            temp_df = cell.data[cell.data.index >= split_moment]
            recent_candle_data = recent_candle_data.combine_first(temp_df)
            if not recent_candle_data.index.is_monotonic_increasing:
                recent_candle_data = await spawn_blocking(
                    sort_data_frame,
                    recent_candle_data,
                )
            candle_data = pd.concat([original_candle_data, recent_candle_data])
            cell.data = candle_data

    async def display_status_information(self):
        async with self.candle_data.read_lock as cell:
            if len(cell.data) == 0:
                # when the app is executed for the first time
                return

        if len(self.price_precisions) == 0:
            # right after the app execution
            return

        # price
        price_precisions = self.price_precisions
        recent_aggregate_trades = slice_deque(self.aggregate_trades, 2 ** (10 + 6))
        for symbol in self.window.data_settings.target_symbols:
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
            self.window.price_labels[symbol].setText(text)

        # bottom information
        if len(self.markets_gone) == 0:
            cumulation_rate = await self.check_candle_data_cumulation_rate()
            first_written_time = None
            last_written_time = None
            realtime_data = self.realtime_data
            if len(realtime_data) > 0:
                if first_written_time is None:
                    first_record = realtime_data[0]
                    first_written_time = first_record.timestamp
                last_record = realtime_data[-1]
                last_written_time = last_record.timestamp
                written_seconds = (last_written_time - first_written_time) / 10**3
            else:
                written_seconds = 0.0
            written_length = timedelta(seconds=written_seconds)
            range_days = written_length.days
            range_hours, remains = divmod(written_length.seconds, 3600)
            range_minutes, remains = divmod(remains, 60)
            written_length_text = f"{range_days}d {range_hours}h {range_minutes}m"

            text = ""
            text += f"24h candle data accumulation rate {cumulation_rate * 100:.2f}%"
            text += "  ⦁  "
            text += f"Realtime data length {written_length_text}"
        else:
            markets_gone = self.markets_gone
            text = (
                f"It seems that {', '.join(markets_gone)} markets are removed by Binance."
                + " You should make a new data folder."
            )

        self.window.label_6.setText(text)

    async def check_candle_data_cumulation_rate(self) -> float:
        # End slicing at previous moment
        # because current moment might still be filling.
        current_moment = to_moment(datetime.now(timezone.utc))
        count_end_moment = current_moment - timedelta(seconds=10)
        count_start_moment = count_end_moment - timedelta(hours=24)

        # Pandas dataframe slicing uses inclusive end.
        count_end_moment -= timedelta(seconds=1)

        async with self.candle_data.read_lock as cell:
            cumulated = len(cell.data[count_start_moment:count_end_moment].dropna())
        needed_moments = 6 * 60 * 24
        cumulation_rate = cumulated / needed_moments

        return cumulation_rate

    async def open_binance_data_page(self):
        await spawn_blocking(webbrowser.open, "https://www.binance.com/en/landing/data")

    async def download_fill_candle_data(self):
        self.download_fill_task.spawn(self._download_fill_candle_data())

    async def _download_fill_candle_data(self):
        unique_task = self.download_fill_task

        # ■■■■■ ask filling type ■■■■■

        filling_type = await overlay(DownloadFillOption())
        if filling_type is None:
            return

        # ■■■■■ prepare target tuples for downloading ■■■■■

        download_presets: list[DownloadPreset] = []
        target_symbols = self.window.data_settings.target_symbols
        if filling_type == 0:
            current_year = datetime.now(timezone.utc).year
            for year in range(2020, current_year):
                for month in range(1, 12 + 1):
                    for symbol in target_symbols:
                        download_presets.append(
                            DownloadPreset(
                                symbol=symbol,
                                unit_size=DownloadUnitSize.MONTHLY,
                                year=year,
                                month=month,
                            )
                        )
        elif filling_type == 1:
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            for month in range(1, current_month):
                for symbol in target_symbols:
                    download_presets.append(
                        DownloadPreset(
                            symbol=symbol,
                            unit_size=DownloadUnitSize.MONTHLY,
                            year=current_year,
                            month=month,
                        )
                    )
        elif filling_type == 2:
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            current_day = datetime.now(timezone.utc).day
            for target_day in range(1, current_day):
                for symbol in target_symbols:
                    download_presets.append(
                        DownloadPreset(
                            symbol=symbol,
                            unit_size=DownloadUnitSize.DAILY,
                            year=current_year,
                            month=current_month,
                            day=target_day,
                        )
                    )
        elif filling_type == 3:
            now = datetime.now(timezone.utc)
            yesterday = now - timedelta(hours=24)
            day_before_yesterday = yesterday - timedelta(hours=24)
            for symbol in target_symbols:
                download_presets.append(
                    DownloadPreset(
                        symbol=symbol,
                        unit_size=DownloadUnitSize.DAILY,
                        year=day_before_yesterday.year,
                        month=day_before_yesterday.month,
                        day=day_before_yesterday.day,
                    ),
                )
                download_presets.append(
                    DownloadPreset(
                        symbol=symbol,
                        unit_size=DownloadUnitSize.DAILY,
                        year=yesterday.year,
                        month=yesterday.month,
                        day=yesterday.day,
                    ),
                )

        random.shuffle(download_presets)

        total_steps = len(download_presets)
        done_steps = 0

        # ■■■■■ play the progress bar ■■■■■

        async def play_progress_bar():
            while True:
                if done_steps == total_steps:
                    progressbar_value = self.window.progressBar_3.value()
                    if progressbar_value == 1000:
                        await sleep(0.1)
                        self.window.progressBar_3.setValue(0)
                        return
                before_value = self.window.progressBar_3.value()
                if before_value < 1000:
                    remaining = (
                        math.ceil(1000 / total_steps * done_steps) - before_value
                    )
                    new_value = before_value + math.ceil(remaining * 0.2)
                    self.window.progressBar_3.setValue(new_value)
                await sleep(0.01)

        bar_task = spawn(play_progress_bar())
        bar_task.add_done_callback(lambda _: self.window.progressBar_3.setValue(0))
        unique_task.add_done_callback(lambda _: bar_task.cancel())

        # ■■■■■ calculate in parellel ■■■■■

        # Gather information about years.
        current_year = datetime.now(timezone.utc).year
        all_years = {t.year for t in download_presets}

        # Download and save historical data by year for lower memory usage.
        # Key is the year, value is the list of download presets.
        classified_download_presets: dict[int, list[DownloadPreset]] = {
            y: [] for y in all_years
        }
        for download_preset in download_presets:
            classified_download_presets[download_preset.year].append(download_preset)

        for preset_year, download_presets in classified_download_presets.items():
            # Make an empty dataframe, but of same types with that of candle data.
            async with self.candle_data.read_lock as cell:
                combined_df = RWLock(cell.data.iloc[0:0].copy())

            async def download_fill(download_preset: DownloadPreset) -> None:
                nonlocal done_steps
                nonlocal combined_df

                returned = await spawn_blocking(download_aggtrade_data, download_preset)
                if returned is not None:
                    new_df = returned
                    async with combined_df.write_lock as cell:
                        new = await spawn_blocking(
                            combine_candle_data, new_df, cell.data
                        )
                        cell.data = new

                done_steps += 1

            fill_tasks = [spawn(download_fill(p)) for p in download_presets]
            unique_task.add_done_callback(lambda _: (t.cancel() for t in fill_tasks))
            await wait(fill_tasks)

            if preset_year < current_year:
                # For data of previous years,
                # save them in the disk.
                async with combined_df.read_lock as cell:
                    await spawn_blocking(
                        cell.data.to_pickle,
                        self.workerpath / f"candle_data_{preset_year}.pickle",
                    )
            else:
                # For data of current year, pass it to this collector worker
                # and store them in the memory.
                async with combined_df.read_lock as cell:
                    async with self.candle_data.write_lock as cell_worker:
                        cell_worker.data = await spawn_blocking(
                            combine_candle_data,
                            cell.data,
                            cell_worker.data,
                        )
                await self._save_candle_data()

        # ■■■■■ add to log ■■■■■

        text = "Filled the candle data with the history data downloaded from Binance"
        logger.info(text)

        # ■■■■■ display to graphs ■■■■■

        spawn(team.transactor.display_lines())
        spawn(team.simulator.display_lines())
        spawn(team.simulator.display_available_years())

    async def add_book_tickers(self, received: dict[str, Any]):
        duration_recorder = DurationRecorder("ADD_BOOK_TICKERS")

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

        duration_recorder.record()

    async def add_mark_price(self, received: list[dict[str, Any]]):
        duration_recorder = DurationRecorder("ADD_MARK_PRICE")

        target_symbols = self.window.data_settings.target_symbols
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

        duration_recorder.record()

    async def add_aggregate_trades(self, received: dict[str, Any]):
        duration_recorder = DurationRecorder("ADD_AGGREGATE_TRADES")

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

        duration_recorder.record()

    async def clear_aggregate_trades(self):
        self.realtime_data.clear()

    async def add_candle_data(self):
        duration_recorder = DurationRecorder("ADD_CANDLE_DATA")

        # Prepare basic infos.
        current_moment = to_moment(datetime.now(timezone.utc))
        before_moment = current_moment - timedelta(seconds=10.0)
        collect_from = int(before_moment.timestamp()) * 1000
        collect_to = int(current_moment.timestamp()) * 1000
        aggregate_trades = self.aggregate_trades

        # Ensure that the data have been watched for long enough.
        first_received_index = aggregate_trades[0].timestamp
        if collect_from <= first_received_index:
            return

        # Collect trades that should be included in the candle.
        collected_aggregate_trades: list[AggregateTrade] = []
        for aggregate_trade in reversed(aggregate_trades):
            if aggregate_trade.timestamp < collect_from - 1000:
                # Go additional 1000 millliseconds backward.
                break
            collected_aggregate_trades.append(aggregate_trade)
        if len(collected_aggregate_trades) == 0:
            return
        collected_aggregate_trades.reverse()  # Sort by time
        collected_aggregate_trades = [
            t
            for t in collected_aggregate_trades
            if collect_from < t.timestamp < collect_to
        ]

        new_values: dict[str, float] = {}
        for symbol in self.window.data_settings.target_symbols:
            symbol_aggregate_trades = [
                t for t in collected_aggregate_trades if t.symbol == symbol
            ]
            self.aggtrade_candle_sizes[symbol] = len(symbol_aggregate_trades)

            if len(symbol_aggregate_trades) > 0:
                open_price = symbol_aggregate_trades[0].price
                high_price = max([t.price for t in symbol_aggregate_trades])
                low_price = min([t.price for t in symbol_aggregate_trades])
                close_price = symbol_aggregate_trades[-1].price
                sum_volume = sum([t.volume for t in symbol_aggregate_trades])
            else:
                async with self.candle_data.read_lock as cell:
                    inspect_sr = cell.data.iloc[-60:][f"{symbol}/CLOSE"].copy()
                inspect_sr = inspect_sr.dropna()
                if len(inspect_sr) == 0:
                    return
                last_price = inspect_sr.tolist()[-1]
                open_price = last_price
                high_price = last_price
                low_price = last_price
                close_price = last_price
                sum_volume = 0.0

            new_values[f"{symbol}/OPEN"] = open_price
            new_values[f"{symbol}/HIGH"] = high_price
            new_values[f"{symbol}/LOW"] = low_price
            new_values[f"{symbol}/CLOSE"] = close_price
            new_values[f"{symbol}/VOLUME"] = sum_volume

        async with self.candle_data.write_lock as cell:
            for column_name, new_data_value in new_values.items():
                cell.data.loc[before_moment, column_name] = np.float32(new_data_value)
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await spawn_blocking(sort_data_frame, cell.data)

        duration_recorder.record()

    async def stop_filling_candle_data(self):
        self.download_fill_task.cancel()

    async def guide_donation(self):
        await overlay(DonationGuide())

    async def check_saved_years(self) -> list[int]:
        years = [
            int(format_numeric(filename))
            for filename in await aiofiles.os.listdir(self.workerpath)
            if filename.startswith("candle_data_") and filename.endswith(".pickle")
        ]
        return years

    async def read_saved_candle_data(self, year: int) -> pd.DataFrame:
        filepath = self.workerpath / f"candle_data_{year}.pickle"
        candle_data: pd.DataFrame = await spawn_blocking(pd.read_pickle, filepath)
        return candle_data
