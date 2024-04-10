import asyncio
import itertools
import logging
import math
import random
import webbrowser
from collections import deque
from datetime import datetime, timedelta, timezone

import aiofiles.os
import numpy as np
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6 import QtWidgets

from solie.common import go, outsource
from solie.overlay import DonationGuide, DownloadFillOption
from solie.utility import (
    ApiRequester,
    ApiStreamer,
    DownloadPreset,
    RWLock,
    add_task_duration,
    combine_candle_data,
    download_aggtrade_data,
    fill_holes_with_aggtrades,
    find_stop_flag,
    format_numeric,
    get_current_moment,
    internet_connected,
    make_stop_flag,
    sort_data_frame,
    standardize_candle_data,
    when_internet_disconnected,
)
from solie.widget import overlay
from solie.window import Window

from .united import team

logger = logging.getLogger(__name__)


class Collector:
    def __init__(self, window: Window, scheduler: AsyncIOScheduler):
        # ■■■■■ for data management ■■■■■

        self.window = window
        self.scheduler = scheduler
        self.workerpath = window.datapath / "collector"

        # ■■■■■ internal memory ■■■■■

        self.price_precisions: dict[str, int] = {}  # Symbol and decimal places
        self.markets_gone: set[str] = set()  # Symbols

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.aggtrade_candle_sizes = {}
        for symbol in window.data_settings.target_symbols:
            self.aggtrade_candle_sizes[symbol] = 0

        # Candle data.
        # It's expected to have only the data of current year,
        # while data of previous years are stored in the disk.
        self.candle_data = RWLock(
            standardize_candle_data(window.data_settings.target_symbols)
        )

        # Realtime data chunks
        field_names = itertools.product(
            window.data_settings.target_symbols,
            ("Best Bid Price", "Best Ask Price", "Mark Price"),
        )
        field_names = [str(field_name) for field_name in field_names]
        dtype = [(field_name, np.float32) for field_name in field_names]
        dtpye = [("index", "datetime64[ns]")] + dtype
        self.realtime_data_chunks = RWLock(
            deque([np.recarray(shape=(0,), dtype=dtpye) for _ in range(2)], maxlen=64)
        )

        # Aggregate trades
        field_names = itertools.product(
            window.data_settings.target_symbols,
            ("Price", "Volume"),
        )
        field_names = [str(field_name) for field_name in field_names]
        dtype = [(field_name, np.float32) for field_name in field_names]
        dtpye = [("index", "datetime64[ns]")] + dtype
        self.aggregate_trades = RWLock(np.recarray(shape=(0,), dtype=dtpye))

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
            self.save_candle_data,
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

        action_menu = QtWidgets.QMenu(self.window)
        self.window.pushButton_13.setMenu(action_menu)

        text = "Open historical data webpage of Binance"
        job = self.open_binance_data_page
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Stop filling candle data"
        job = self.stop_filling_candle_data
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)

    async def load(self):
        await aiofiles.os.makedirs(self.workerpath, exist_ok=True)

        # candle data
        current_year = datetime.now(timezone.utc).year
        async with self.candle_data.write_lock as cell:
            filepath = self.workerpath / f"candle_data_{current_year}.pickle"
            if await aiofiles.os.path.isfile(filepath):
                df: pd.DataFrame = await go(pd.read_pickle, filepath)
                if not df.index.is_monotonic_increasing:
                    df = await go(sort_data_frame, df)
                cell.data = df

    async def organize_data(self):
        start_time = datetime.now(timezone.utc)

        async with self.candle_data.write_lock as cell:
            original_index = cell.data.index
            if not cell.data.index.is_unique:
                unique_index = original_index.drop_duplicates()
                cell.data = cell.data.reindex(unique_index)
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await go(sort_data_frame, cell.data)

        async with self.realtime_data_chunks.write_lock as cell:
            cell.data[-1].sort(order="index")
            if len(cell.data[-1]) > 2**16:
                new_chunk = cell.data[-1][0:0].copy()
                cell.data.append(new_chunk)
                del new_chunk

        async with self.aggregate_trades.write_lock as cell:
            cell.data.sort(order="index")
            last_index = cell.data[-1]["index"]
            slice_from = last_index - np.timedelta64(60, "s")
            mask = cell.data["index"] > slice_from
            cell.data = cell.data[mask].copy()

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        add_task_duration("collector_organize_data", duration)

    async def save_candle_data(self):
        # ■■■■■ default values ■■■■■

        current_year = datetime.now(timezone.utc).year
        filepath = self.workerpath / f"candle_data_{current_year}.pickle"
        filepath_new = self.workerpath / f"candle_data_{current_year}.pickle.new"
        filepath_backup = self.workerpath / f"candle_data_{current_year}.pickle.backup"

        async with self.candle_data.read_lock as cell:
            mask = cell.data.index.year == current_year  # type:ignore
            year_df: pd.DataFrame = cell.data[mask].copy()

        # ■■■■■ make a new file ■■■■■

        await go(year_df.to_pickle, filepath_new)

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

        payload = {}
        response = await self.api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload=payload,
        )
        about_exchange = response

        for about_symbol in about_exchange["symbols"]:
            symbol = about_symbol["symbol"]

            about_filter = {}
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

        current_moment = get_current_moment()
        split_moment = current_moment - timedelta(days=2)

        # ■■■■■ fill holes ■■■■■

        full_symbols: set[str] = set()
        request_count = 0

        # only the recent part
        async with self.candle_data.read_lock as cell:
            recent_candle_data = cell.data[cell.data.index >= split_moment].copy()

        did_fill = False

        target_symbols = self.window.data_settings.target_symbols
        while len(full_symbols) < len(target_symbols) and request_count < 10:
            for symbol in target_symbols:
                if symbol in full_symbols:
                    continue

                from_moment = current_moment - timedelta(hours=24)
                until_moment = current_moment - timedelta(minutes=1)

                inspect_df: pd.DataFrame = recent_candle_data[symbol][
                    from_moment:until_moment
                ]  # type:ignore
                base_index = inspect_df.dropna().index
                temp_sr = pd.Series(0, index=base_index)
                written_moments = len(temp_sr)

                if written_moments == (86400 - 60) / 10 + 1:
                    # case when there are no holes
                    full_symbols.add(symbol)
                    continue

                if from_moment not in temp_sr.index:
                    temp_sr[from_moment] = np.nan
                if until_moment not in temp_sr.index:
                    temp_sr[until_moment] = np.nan
                temp_sr = await go(temp_sr.asfreq, "10S")
                isnan_sr = await go(temp_sr.isna)
                nan_index = isnan_sr[isnan_sr == 1].index
                moment_to_fill_from: datetime = nan_index[0]  # type:ignore

                # request historical aggtrade data
                aggtrades = {}
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
                    for aggtrade in response:
                        aggtrade_id = aggtrade["a"]
                        aggtrades[aggtrade_id] = aggtrade
                    last_fetched_id = max(aggtrades.keys())
                    last_fetched_time = datetime.fromtimestamp(
                        aggtrades[last_fetched_id]["T"] / 1000, tz=timezone.utc
                    )

                recent_candle_data = await go(
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
                recent_candle_data = await go(
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
        async with self.aggregate_trades.read_lock as cell:
            ar = cell.data.copy()
        price_precisions = self.price_precisions

        for symbol in self.window.data_settings.target_symbols:
            temp_ar = ar[str((symbol, "Price"))]
            temp_ar = temp_ar[temp_ar != 0]
            if len(temp_ar) > 0:
                price_precision = price_precisions[symbol]
                latest_price = temp_ar[-1]
                text = f"＄{latest_price:.{price_precision}f}"
            else:
                text = "Unavailable"
            self.window.price_labels[symbol].setText(text)

        # bottom information
        if len(self.markets_gone) == 0:
            cumulation_rate = await self.check_candle_data_cumulation_rate()
            async with self.realtime_data_chunks.read_lock as cell:
                chunk_count = len(cell.data)
            first_written_time = None
            last_written_time = None
            for turn in range(chunk_count):
                async with self.realtime_data_chunks.read_lock as cell:
                    if len(cell.data[turn]) > 0:
                        if first_written_time is None:
                            first_record = cell.data[turn][0]
                            first_written_time = first_record["index"]
                            del first_record
                        last_record = cell.data[turn][-1]
                        last_written_time = last_record["index"]
                        del last_record
            if first_written_time is not None and last_written_time is not None:
                written_seconds = last_written_time - first_written_time
                written_seconds = written_seconds.astype(np.int64) / 10**9
            else:
                written_seconds = 0
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
        current_moment = get_current_moment()
        count_start_moment = current_moment - timedelta(hours=24)
        async with self.candle_data.read_lock as cell:
            cumulated_moments = len(cell.data[count_start_moment:].dropna())
        needed_moments = 24 * 60 * 60 / 10
        cumulation_rate = min(1.0, (cumulated_moments + 2) / needed_moments)
        return cumulation_rate

    async def open_binance_data_page(self):
        await go(webbrowser.open, "https://www.binance.com/en/landing/data")

    async def download_fill_candle_data(self):
        # ■■■■■ ask filling type ■■■■■

        overlay_widget = await overlay(
            "Choose the range to fill",
            DownloadFillOption(),
        )
        filling_type = overlay_widget.result

        if filling_type is None:
            return

        # ■■■■■ prepare target tuples for downloading ■■■■■

        task_id = make_stop_flag("download_fill_candle_data")

        download_presets: list[DownloadPreset] = []
        target_symbols = self.window.data_settings.target_symbols
        if filling_type == 0:
            current_year = datetime.now(timezone.utc).year
            for year in range(2020, current_year):
                for month in range(1, 12 + 1):
                    for symbol in target_symbols:
                        download_presets.append(
                            DownloadPreset(
                                symbol,
                                "monthly",
                                year,
                                month,
                            )
                        )
        elif filling_type == 1:
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            for month in range(1, current_month):
                for symbol in target_symbols:
                    download_presets.append(
                        DownloadPreset(
                            symbol,
                            "monthly",
                            current_year,
                            month,
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
                            symbol,
                            "daily",
                            current_year,
                            current_month,
                            target_day,
                        )
                    )
        elif filling_type == 3:
            now = datetime.now(timezone.utc)
            yesterday = now - timedelta(hours=24)
            day_before_yesterday = yesterday - timedelta(hours=24)
            for symbol in target_symbols:
                download_presets.append(
                    DownloadPreset(
                        symbol,
                        "daily",
                        day_before_yesterday.year,
                        day_before_yesterday.month,
                        day_before_yesterday.day,
                    ),
                )
                download_presets.append(
                    DownloadPreset(
                        symbol,
                        "daily",
                        yesterday.year,
                        yesterday.month,
                        yesterday.day,
                    ),
                )

        random.shuffle(download_presets)

        total_steps = len(download_presets)
        done_steps = 0

        # ■■■■■ play the progress bar ■■■■■

        async def play_progress_bar():
            while True:
                if find_stop_flag("download_fill_candle_data", task_id):
                    self.window.progressBar_3.setValue(0)
                    return
                else:
                    if done_steps == total_steps:
                        progressbar_value = self.window.progressBar_3.value()
                        if progressbar_value == 1000:
                            await asyncio.sleep(0.1)
                            self.window.progressBar_3.setValue(0)
                            return
                    before_value = self.window.progressBar_3.value()
                    if before_value < 1000:
                        remaining = (
                            math.ceil(1000 / total_steps * done_steps) - before_value
                        )
                        new_value = before_value + math.ceil(remaining * 0.2)
                        self.window.progressBar_3.setValue(new_value)
                    await asyncio.sleep(0.01)

        asyncio.create_task(play_progress_bar())

        # ■■■■■ calculate in parellel ■■■■■

        # Gather information about years.
        current_year = datetime.now(timezone.utc).year
        all_years: set[int] = {t.year for t in download_presets}

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

                if find_stop_flag("download_fill_candle_data", task_id):
                    return

                returned = await go(download_aggtrade_data, download_preset)
                if returned is not None:
                    new_df = returned
                    async with combined_df.write_lock as cell:
                        new = await go(combine_candle_data, new_df, cell.data)
                        cell.data = new

                done_steps += 1

            tasks = [asyncio.create_task(download_fill(p)) for p in download_presets]
            await asyncio.wait(tasks)

            if preset_year < current_year:
                # For data of previous years,
                # save them in the disk.
                async with combined_df.read_lock as cell:
                    await go(
                        cell.data.to_pickle,
                        self.workerpath / f"candle_data_{preset_year}.pickle",
                    )
            else:
                # For data of current year, pass it to this collector worker
                # and store them in the memory.
                async with combined_df.read_lock as cell:
                    async with self.candle_data.write_lock as cell_worker:
                        cell_worker.data = await go(
                            combine_candle_data,
                            cell.data,
                            cell_worker.data,
                        )
                await self.save_candle_data()

        # ■■■■■ add to log ■■■■■

        text = "Filled the candle data with the history data downloaded from Binance"
        logger.info(text)

        # ■■■■■ display to graphs ■■■■■

        asyncio.create_task(team.transactor.display_lines())
        asyncio.create_task(team.simulator.display_lines())
        asyncio.create_task(team.simulator.display_available_years())

    async def add_book_tickers(self, received: dict):
        start_time = datetime.now(timezone.utc)
        symbol = received["s"]
        best_bid = received["b"]
        best_ask = received["a"]
        event_time = np.datetime64(received["E"] * 10**6, "ns")
        async with self.realtime_data_chunks.write_lock as cell:
            original_size = cell.data[-1].shape[0]
            cell.data[-1].resize(original_size + 1, refcheck=False)
            cell.data[-1][-1]["index"] = event_time
            find_key = str((symbol, "Best Bid Price"))
            cell.data[-1][-1][find_key] = best_bid
            find_key = str((symbol, "Best Ask Price"))
            cell.data[-1][-1][find_key] = best_ask
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        add_task_duration("add_book_tickers", duration)

    async def add_mark_price(self, received: list):
        start_time = datetime.now(timezone.utc)
        target_symbols = self.window.data_settings.target_symbols
        event_time = np.datetime64(received[0]["E"] * 10**6, "ns")
        filtered_data = {}
        for about_mark_price in received:
            symbol = about_mark_price["s"]
            if symbol in target_symbols:
                mark_price = float(about_mark_price["p"])
                filtered_data[symbol] = mark_price
        async with self.realtime_data_chunks.write_lock as cell:
            original_size = cell.data[-1].shape[0]
            cell.data[-1].resize(original_size + 1, refcheck=False)
            cell.data[-1][-1]["index"] = event_time
            for symbol, mark_price in filtered_data.items():
                find_key = str((symbol, "Mark Price"))
                cell.data[-1][-1][find_key] = mark_price
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        add_task_duration("add_mark_price", duration)

    async def add_aggregate_trades(self, received: dict):
        start_time = datetime.now(timezone.utc)
        symbol = received["s"]
        price = float(received["p"])
        volume = float(received["q"])
        trade_time = np.datetime64(received["T"] * 10**6, "ns")
        async with self.aggregate_trades.write_lock as cell:
            original_size = cell.data.shape[0]
            cell.data.resize(original_size + 1, refcheck=False)
            cell.data[-1]["index"] = trade_time
            cell.data[-1][str((symbol, "Price"))] = price
            cell.data[-1][str((symbol, "Volume"))] = volume
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        add_task_duration("add_aggregate_trades", duration)

    async def clear_aggregate_trades(self):
        async with self.aggregate_trades.write_lock as cell:
            cell.data = cell.data[0:0].copy()

    async def add_candle_data(self):
        current_moment = get_current_moment()
        before_moment = current_moment - timedelta(seconds=10)

        async with self.aggregate_trades.read_lock as cell:
            data_length = len(cell.data)
        if data_length == 0:
            return

        for _ in range(20):
            async with self.aggregate_trades.read_lock as cell:
                last_received_index = cell.data[-1]["index"]
            if np.datetime64(current_moment) < last_received_index:
                break
            await asyncio.sleep(0.1)

        async with self.aggregate_trades.read_lock as cell:
            aggregate_trades = cell.data.copy()

        first_received_index = aggregate_trades[0]["index"]
        if first_received_index >= np.datetime64(before_moment):
            return

        new_datas = {}

        for symbol in self.window.data_settings.target_symbols:
            block_start_timestamp = before_moment.timestamp()
            block_end_timestamp = current_moment.timestamp()

            index_ar = aggregate_trades["index"].astype(np.int64) / 10**9
            after_start_mask = block_start_timestamp <= index_ar
            before_end_mask = index_ar < block_end_timestamp
            block_ar = aggregate_trades[after_start_mask & before_end_mask]
            block_ar = block_ar[block_ar[str((symbol, "Volume"))] != 0]
            self.aggtrade_candle_sizes[symbol] = block_ar.size

            if len(block_ar) > 0:
                open_price = block_ar[0][str((symbol, "Price"))]
                high_price = block_ar[str((symbol, "Price"))].max()
                low_price = block_ar[str((symbol, "Price"))].min()
                close_price = block_ar[-1][str((symbol, "Price"))]
                sum_volume = block_ar[str((symbol, "Volume"))].sum()
            else:
                async with self.candle_data.read_lock as cell:
                    inspect_sr = cell.data.iloc[-60:][(symbol, "Close")].copy()
                inspect_sr = inspect_sr.dropna()
                if len(inspect_sr) == 0:
                    return
                last_price = inspect_sr.tolist()[-1]
                open_price = last_price
                high_price = last_price
                low_price = last_price
                close_price = last_price
                sum_volume = 0

            new_datas[(symbol, "Open")] = open_price
            new_datas[(symbol, "High")] = high_price
            new_datas[(symbol, "Low")] = low_price
            new_datas[(symbol, "Close")] = close_price
            new_datas[(symbol, "Volume")] = sum_volume

        async with self.candle_data.write_lock as cell:
            for column_name, new_data_value in new_datas.items():
                cell.data.loc[before_moment, column_name] = new_data_value
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await go(sort_data_frame, cell.data)

        duration = (datetime.now(timezone.utc) - current_moment).total_seconds()
        add_task_duration("add_candle_data", duration)

    async def stop_filling_candle_data(self):
        make_stop_flag("download_fill_candle_data")

    async def guide_donation(self):
        await overlay(
            "Support Solie",
            DonationGuide(),
        )

    async def check_saved_years(self) -> list[int]:
        years = [
            int(format_numeric(filename))
            for filename in await aiofiles.os.listdir(self.workerpath)
            if filename.startswith("candle_data_") and filename.endswith(".pickle")
        ]
        return years

    async def read_saved_candle_data(self, year: int) -> pd.DataFrame:
        filepath = self.workerpath / f"candle_data_{year}.pickle"
        candle_data: pd.DataFrame = await go(pd.read_pickle, filepath)
        return candle_data
