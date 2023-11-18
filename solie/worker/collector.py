import asyncio
import calendar
import itertools
import math
import os
import random
from collections import deque
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import solie
from solie.instrument.api_requester import ApiRequester
from solie.instrument.api_streamer import ApiStreamer
from solie.instrument.rw_lock import RWLock
from solie.recipe import (
    check_internet,
    combine_candle_datas,
    download_aggtrade_data,
    fill_holes_with_aggtrades,
    open_browser,
    remember_task_durations,
    simply_format,
    sort_dataframe,
    standardize,
    stop_flag,
    user_settings,
)
from solie.shelf.donation_guide import DonationGuide
from solie.shelf.download_fill_option import DownloadFillOption


class Collector:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = user_settings.get_app_settings()["datapath"] + "/collector"
        os.makedirs(self.workerpath, exist_ok=True)

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {
            "price_precisions": {},
            "markets_gone": [],
        }

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.aggtrade_candle_sizes = {}
        for symbol in user_settings.get_data_settings()["target_symbols"]:
            self.aggtrade_candle_sizes[symbol] = 0

        # candle data
        self.candle_data = RWLock(standardize.candle_data())

        # realtime data chunks
        field_names = itertools.product(
            user_settings.get_data_settings()["target_symbols"],
            ("Best Bid Price", "Best Ask Price", "Mark Price"),
        )
        field_names = [str(field_name) for field_name in field_names]
        dtype = [(field_name, np.float32) for field_name in field_names]
        dtpye = [("index", "datetime64[ns]")] + dtype
        self.realtime_data_chunks = RWLock(
            deque([np.recarray(shape=(0,), dtype=dtpye) for _ in range(2)], maxlen=64)
        )

        # aggregate trades
        field_names = itertools.product(
            user_settings.get_data_settings()["target_symbols"],
            ("Price", "Volume"),
        )
        field_names = [str(field_name) for field_name in field_names]
        dtype = [(field_name, np.float32) for field_name in field_names]
        dtpye = [("index", "datetime64[ns]")] + dtype
        self.aggregate_trades = RWLock(np.recarray(shape=(0,), dtype=dtpye))

        # ■■■■■ repetitive schedules ■■■■■

        solie.window.scheduler.add_job(
            self.display_status_information,
            trigger="cron",
            second="*",
        )
        solie.window.scheduler.add_job(
            self.fill_candle_data_holes,
            trigger="cron",
            second="*/10",
        )
        solie.window.scheduler.add_job(
            self.add_candle_data,
            trigger="cron",
            second="*/10",
        )
        solie.window.scheduler.add_job(
            self.organize_data,
            trigger="cron",
            minute="*",
        )
        solie.window.scheduler.add_job(
            self.get_exchange_information,
            trigger="cron",
            minute="*",
        )
        solie.window.scheduler.add_job(
            self.save_candle_data,
            trigger="cron",
            hour="*",
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = {
            "MARK_PRICE": ApiStreamer(
                "wss://fstream.binance.com/ws/!markPrice@arr@1s",
                self.add_mark_price,
            ),
        }
        for symbol in user_settings.get_data_settings()["target_symbols"]:
            api_streamer = ApiStreamer(
                f"wss://fstream.binance.com/ws/{symbol.lower()}@bookTicker",
                self.add_book_tickers,
            )
            self.api_streamers[f"BOOK_TICKER_{symbol}"] = api_streamer
            api_streamer = ApiStreamer(
                f"wss://fstream.binance.com/ws/{symbol.lower()}@aggTrade",
                self.add_aggregate_trades,
            )
            self.api_streamers[f"AGG_TRADE_{symbol}"] = api_streamer

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functions = []
        check_internet.add_connected_functions(connected_functions)

        disconnected_functions = [
            lambda: self.clear_aggregate_trades(),
        ]
        check_internet.add_disconnected_functions(disconnected_functions)

    async def load(self, *args, **kwargs):
        # candle data
        years = [
            int(simply_format.numeric(filename))
            for filename in os.listdir(self.workerpath)
            if filename.startswith("candle_data_") and filename.endswith(".pickle")
        ]
        async with self.candle_data.write_lock as wrapper:
            inner = wrapper.inner
            divided_datas = [inner]
            for year in years:
                filepath = f"{self.workerpath}/candle_data_{year}.pickle"
                more_df = pd.read_pickle(filepath)
                divided_datas.append(more_df)
            concatenated = pd.concat(divided_datas)
            if not concatenated.index.is_monotonic_increasing:
                concatenated = concatenated.sort_index()
            wrapper.replace(concatenated)
        await asyncio.sleep(0)

    async def organize_data(self, *args, **kwargs):
        start_time = datetime.now(timezone.utc)

        async with self.candle_data.write_lock as wrapper:
            df = wrapper.inner
            original_index = df.index
            unique_index = original_index.drop_duplicates()
            df = df.reindex(unique_index)
            df = df.sort_index()
            df = df.asfreq("10S")
            df = df.astype(np.float32)
            wrapper.replace(df)

        async with self.realtime_data_chunks.write_lock as wrapper:
            inner = wrapper.inner
            inner[-1].sort(order="index")
            if len(inner[-1]) > 2**16:
                new_chunk = inner[-1][0:0].copy()
                inner.append(new_chunk)
                del new_chunk

        async with self.aggregate_trades.write_lock as wrapper:
            inner = wrapper.inner
            inner.sort(order="index")
            last_index = inner[-1]["index"]
            slice_from = last_index - np.timedelta64(60, "s")
            mask = inner["index"] > slice_from
            wrapper.replace(inner[mask].copy())

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        remember_task_durations.add("collector_organize_data", duration)

    async def save_candle_data(self, *args, **kwargs):
        # ■■■■■ default values ■■■■■

        current_year = datetime.now(timezone.utc).year
        filepath = f"{self.workerpath}/candle_data_{current_year}.pickle"

        async with self.candle_data.read_lock as wrapper:
            df = wrapper.inner
            year_df = df[df.index.year == current_year].copy()  # type:ignore

        # ■■■■■ make a new file ■■■■■

        year_df.to_pickle(filepath + ".new")

        # ■■■■■ safely replace the existing file ■■■■■

        try:
            os.remove(filepath + ".backup")
        except FileNotFoundError:
            pass

        try:
            os.rename(filepath, filepath + ".backup")
        except FileNotFoundError:
            pass

        try:
            os.rename(filepath + ".new", filepath)
        except FileNotFoundError:
            pass

    async def save_all_years_candle_data(self, *args, **kwargs):
        async with self.candle_data.read_lock as wrapper:
            inner = wrapper.inner
            years_sr = inner.index.year.drop_duplicates()  # type:ignore
            years = years_sr.tolist()

        for year in years:
            async with self.candle_data.read_lock as wrapper:
                df = wrapper.inner
                year_df = df[df.index.year == year].copy()  # type:ignore
            filepath = f"{self.workerpath}/candle_data_{year}.pickle"
            year_df.to_pickle(filepath)

    async def get_exchange_information(self, *args, **kwargs):
        if not check_internet.connected():
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
            self.secret_memory["price_precisions"][symbol] = price_precision

    async def fill_candle_data_holes(self, *args, **kwargs):
        # ■■■■■ check internet connection ■■■■■

        if not check_internet.connected():
            return

        # ■■■■■ moments ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        split_moment = current_moment - timedelta(days=2)

        # ■■■■■ fill holes ■■■■■

        markets_gone = []
        full_symbols = []
        request_count = 0

        # only the recent part
        async with self.candle_data.read_lock as wrapper:
            df = wrapper.inner
            recent_candle_data = df[df.index >= split_moment].copy()

        target_symbols = user_settings.get_data_settings()["target_symbols"]
        while len(full_symbols) < len(target_symbols) and request_count < 10:
            for symbol in target_symbols:
                if symbol in full_symbols:
                    continue

                recent_candle_data = await solie.event_loop.run_in_executor(
                    solie.process_pool, sort_dataframe.do, recent_candle_data
                )

                from_moment = current_moment - timedelta(hours=24)
                until_moment = current_moment - timedelta(minutes=1)

                inspect_df = recent_candle_data[symbol][from_moment:until_moment]
                base_index = inspect_df.dropna().index
                temp_sr = pd.Series(0, index=base_index)
                written_moments = len(temp_sr)

                if written_moments == (86400 - 60) / 10 + 1:
                    # case when there are no holes
                    full_symbols.append(symbol)
                    continue

                if from_moment not in temp_sr.index:
                    temp_sr[from_moment] = np.nan
                if until_moment not in temp_sr.index:
                    temp_sr[until_moment] = np.nan
                temp_sr = temp_sr.asfreq("10S")
                isnan_sr = temp_sr.isna()
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
                        if symbol not in markets_gone:
                            markets_gone.append(symbol)
                        break
                    for aggtrade in response:
                        aggtrade_id = aggtrade["a"]
                        aggtrades[aggtrade_id] = aggtrade
                    last_fetched_id = max(aggtrades.keys())
                    last_fetched_time = datetime.fromtimestamp(
                        aggtrades[last_fetched_id]["T"] / 1000, tz=timezone.utc
                    )

                recent_candle_data = await solie.event_loop.run_in_executor(
                    solie.process_pool,
                    fill_holes_with_aggtrades.do,
                    symbol,
                    recent_candle_data,
                    aggtrades,
                    moment_to_fill_from,
                    last_fetched_time,
                )
        self.secret_memory["markets_gone"] = markets_gone

        # combine
        async with self.candle_data.write_lock as wrapper:
            df = wrapper.inner
            original_candle_data = df[df.index < split_moment]
            # in case the other data is added during the task
            # read the data again
            temp_df = df[df.index >= split_moment]
            recent_candle_data = recent_candle_data.combine_first(temp_df)
            recent_candle_data = recent_candle_data.sort_index()
            candle_data = pd.concat([original_candle_data, recent_candle_data])
            wrapper.replace(candle_data)

    async def display_status_information(self, *args, **kwargs):
        async with self.candle_data.read_lock as wrapper:
            inner = wrapper.inner
            if len(inner) == 0:
                # when the app is executed for the first time
                return

        if len(self.secret_memory["price_precisions"]) == 0:
            # right after the app execution
            return

        # price
        async with self.aggregate_trades.read_lock as wrapper:
            ar = wrapper.inner.copy()
        price_precisions = self.secret_memory["price_precisions"]

        for symbol in user_settings.get_data_settings()["target_symbols"]:
            temp_ar = ar[str((symbol, "Price"))]
            temp_ar = temp_ar[temp_ar != 0]
            if len(temp_ar) > 0:
                price_precision = price_precisions[symbol]
                latest_price = temp_ar[-1]
                text = f"＄{latest_price:.{price_precision}f}"
            else:
                text = "Unavailable"
            solie.window.price_labels[symbol].setText(text)

        # bottom information
        if len(self.secret_memory["markets_gone"]) == 0:
            cumulation_rate = await self.get_candle_data_cumulation_rate()
            async with self.realtime_data_chunks.read_lock as wrapper:
                chunk_count = len(wrapper.inner)
            first_written_time = None
            last_written_time = None
            for turn in range(chunk_count):
                async with self.realtime_data_chunks.read_lock as wrapper:
                    inner = wrapper.inner
                    if len(inner[turn]) > 0:
                        if first_written_time is None:
                            first_record = inner[turn][0]
                            first_written_time = first_record["index"]
                            del first_record
                        last_record = inner[turn][-1]
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
            markets_gone = self.secret_memory["markets_gone"]
            if len(markets_gone) == 1:
                text = f"It seems that {markets_gone[0]} market is removed by Binance. You should make a new data folder."
            else:
                text = f"It seems that {', '.join(markets_gone)} markets are removed by Binance. You should make a new data folder."

        solie.window.label_6.setText(text)

    async def get_candle_data_cumulation_rate(self, *args, **kwargs):
        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        count_start_moment = current_moment - timedelta(hours=24)
        async with self.candle_data.read_lock as wrapper:
            df = wrapper.inner
            cumulated_moments = len(df[count_start_moment:].dropna())
        needed_moments = 24 * 60 * 60 / 10
        cumulation_rate = min(float(1), (cumulated_moments + 1) / needed_moments)
        return cumulation_rate

    async def open_binance_data_page(self, *args, **kwargs):
        open_browser.do("https://www.binance.com/en/landing/data")

    async def download_fill_candle_data(self, *args, **kwargs):
        # ■■■■■ ask filling type ■■■■■

        answer_container = {"filling_type": None}

        formation = [
            "Choose the range to fill",
            DownloadFillOption,
            True,
            [answer_container],
        ]

        await solie.window.overlap(formation)

        filling_type = answer_container["filling_type"]
        if filling_type is None:
            return

        # ■■■■■ prepare target tuples for downloading ■■■■■

        task_id = stop_flag.make("download_fill_candle_data")

        target_tuples = []
        target_symbols = user_settings.get_data_settings()["target_symbols"]
        if filling_type == 0:
            current_year = datetime.now(timezone.utc).year
            for year in range(2020, current_year):
                for month in range(1, 12 + 1):
                    for symbol in target_symbols:
                        target_tuples.append(
                            (
                                symbol,
                                "monthly",
                                year,
                                month,
                            )
                        )
        if filling_type == 1:
            current_year = datetime.now(timezone.utc).year
            for year in range(2020, current_year):
                for month in range(1, 12 + 1):
                    days_in_month = calendar.monthrange(2019, 1)[1]
                    for day in range(1, days_in_month + 1):
                        for symbol in target_symbols:
                            target_tuples.append(
                                (
                                    symbol,
                                    "daily",
                                    year,
                                    month,
                                    day,
                                )
                            )
        if filling_type == 2:
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            for month in range(1, current_month):
                for symbol in target_symbols:
                    target_tuples.append(
                        (
                            symbol,
                            "monthly",
                            current_year,
                            month,
                        )
                    )
        if filling_type == 3:
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            for month in range(1, current_month):
                days_in_month = calendar.monthrange(2019, 1)[1]
                for day in range(1, days_in_month + 1):
                    for symbol in target_symbols:
                        target_tuples.append(
                            (
                                symbol,
                                "daily",
                                current_year,
                                month,
                                day,
                            )
                        )
        elif filling_type == 4:
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            current_day = datetime.now(timezone.utc).day
            for target_day in range(1, current_day):
                for symbol in target_symbols:
                    target_tuples.append(
                        (
                            symbol,
                            "daily",
                            current_year,
                            current_month,
                            target_day,
                        )
                    )
        elif filling_type == 5:
            now = datetime.now(timezone.utc)
            yesterday = now - timedelta(hours=24)
            day_before_yesterday = yesterday - timedelta(hours=24)
            for symbol in target_symbols:
                target_tuples.append(
                    (
                        symbol,
                        "daily",
                        day_before_yesterday.year,
                        day_before_yesterday.month,
                        day_before_yesterday.day,
                    ),
                )
                target_tuples.append(
                    (
                        symbol,
                        "daily",
                        yesterday.year,
                        yesterday.month,
                        yesterday.day,
                    ),
                )

        total_steps = len(target_tuples)
        done_steps = 0

        # ■■■■■ play the progress bar ■■■■■

        async def play_progress_bar():
            while True:
                if stop_flag.find("download_fill_candle_data", task_id):
                    solie.window.progressBar_3.setValue(0)
                    return
                else:
                    if done_steps == total_steps:
                        progressbar_value = solie.window.progressBar_3.value()
                        if progressbar_value == 1000:
                            await asyncio.sleep(0.1)
                            solie.window.progressBar_3.setValue(0)
                            return
                    before_value = solie.window.progressBar_3.value()
                    if before_value < 1000:
                        remaining = (
                            math.ceil(1000 / total_steps * done_steps) - before_value
                        )
                        new_value = before_value + math.ceil(remaining * 0.2)
                        solie.window.progressBar_3.setValue(new_value)
                    await asyncio.sleep(0.01)

        asyncio.create_task(play_progress_bar())

        # ■■■■■ calculate in parellel ■■■■■

        random.shuffle(target_tuples)
        lanes = solie.process_count
        chunk_size = math.ceil(len(target_tuples) / lanes)
        target_tuple_chunks = []
        for turn in range(lanes):
            new_chunk = target_tuples[turn * chunk_size : (turn + 1) * chunk_size]
            target_tuple_chunks.append(new_chunk)

        async with self.candle_data.read_lock as wrapper:
            inner = wrapper.inner
            combined_df = RWLock(inner.iloc[0:0].copy())

        async def download_fill(target_tuple_chunk):
            nonlocal done_steps
            nonlocal combined_df

            for target_tuple in target_tuple_chunk:
                if stop_flag.find("download_fill_candle_data", task_id):
                    return
                returned = await solie.event_loop.run_in_executor(
                    solie.process_pool,
                    download_aggtrade_data.do,
                    target_tuple,
                )
                if returned is not None:
                    new_df = returned
                    async with combined_df.write_lock as wrapper:
                        inner = wrapper.inner
                        new = await solie.event_loop.run_in_executor(
                            solie.process_pool,
                            combine_candle_datas.do,
                            new_df,
                            inner,
                        )
                        wrapper.replace(new)
                done_steps += 1

        await asyncio.gather(*[download_fill(chunk) for chunk in target_tuple_chunks])

        if stop_flag.find("download_fill_candle_data", task_id):
            return

        # ■■■■■ combine ■■■■■

        async with combined_df.read_lock as wrapper:
            combined_df_inner = wrapper.inner

        async with self.candle_data.write_lock as wrapper:
            inner = wrapper.inner
            df = await solie.event_loop.run_in_executor(
                solie.process_pool,
                combine_candle_datas.do,
                combined_df_inner,
                inner,
            )
            wrapper.replace(df)

        # ■■■■■ save ■■■■■

        await self.save_all_years_candle_data()

        # ■■■■■ add to log ■■■■■

        text = "Filled the candle data with the history data downloaded from Binance"
        solie.logger.info(text)

        # ■■■■■ display to graphs ■■■■■

        asyncio.create_task(solie.window.transactor.display_lines())
        asyncio.create_task(solie.window.simulator.display_lines())

    async def add_book_tickers(self, *args, **kwargs):
        received: dict = kwargs.get("received")  # type:ignore
        start_time = datetime.now(timezone.utc)
        symbol = received["s"]
        best_bid = received["b"]
        best_ask = received["a"]
        event_time = np.datetime64(received["E"] * 10**6, "ns")
        async with self.realtime_data_chunks.write_lock as wrapper:
            inner = wrapper.inner
            original_size = inner[-1].shape[0]
            inner[-1].resize(original_size + 1, refcheck=False)
            inner[-1][-1]["index"] = event_time
            find_key = str((symbol, "Best Bid Price"))
            inner[-1][-1][find_key] = best_bid
            find_key = str((symbol, "Best Ask Price"))
            inner[-1][-1][find_key] = best_ask
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        remember_task_durations.add("add_book_tickers", duration)

    async def add_mark_price(self, *args, **kwargs):
        received: dict = kwargs.get("received")  # type:ignore
        start_time = datetime.now(timezone.utc)
        target_symbols = user_settings.get_data_settings()["target_symbols"]
        event_time = np.datetime64(received[0]["E"] * 10**6, "ns")
        filtered_data = {}
        for about_mark_price in received:
            symbol = about_mark_price["s"]
            if symbol in target_symbols:
                mark_price = float(about_mark_price["p"])
                filtered_data[symbol] = mark_price
        async with self.realtime_data_chunks.write_lock as wrapper:
            inner = wrapper.inner
            original_size = inner[-1].shape[0]
            inner[-1].resize(original_size + 1, refcheck=False)
            inner[-1][-1]["index"] = event_time
            for symbol, mark_price in filtered_data.items():
                find_key = str((symbol, "Mark Price"))
                inner[-1][-1][find_key] = mark_price
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        remember_task_durations.add("add_mark_price", duration)

    async def add_aggregate_trades(self, *args, **kwargs):
        received: dict = kwargs.get("received")  # type:ignore
        start_time = datetime.now(timezone.utc)
        symbol = received["s"]
        price = float(received["p"])
        volume = float(received["q"])
        trade_time = np.datetime64(received["T"] * 10**6, "ns")
        async with self.aggregate_trades.write_lock as wrapper:
            inner = wrapper.inner
            original_size = inner.shape[0]
            inner.resize(original_size + 1, refcheck=False)
            inner[-1]["index"] = trade_time
            inner[-1][str((symbol, "Price"))] = price
            inner[-1][str((symbol, "Volume"))] = volume
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        remember_task_durations.add("add_aggregate_trades", duration)

    async def clear_aggregate_trades(self, *args, **kwargs):
        async with self.aggregate_trades.write_lock as wrapper:
            inner = wrapper.inner
            new = inner[0:0].copy()
            wrapper.replace(new)

    async def add_candle_data(self, *args, **kwargs):
        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        async with self.aggregate_trades.read_lock as wrapper:
            data_length = len(wrapper.inner)
        if data_length == 0:
            return

        for _ in range(20):
            async with self.aggregate_trades.read_lock as wrapper:
                last_received_index = wrapper.inner[-1]["index"]
            if np.datetime64(current_moment) < last_received_index:
                break
            await asyncio.sleep(0.1)

        async with self.aggregate_trades.read_lock as wrapper:
            aggregate_trades = wrapper.inner.copy()

        first_received_index = aggregate_trades[0]["index"]
        if first_received_index >= np.datetime64(before_moment):
            return

        new_datas = {}

        for symbol in user_settings.get_data_settings()["target_symbols"]:
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
                async with self.candle_data.read_lock as wrapper:
                    df = wrapper.inner
                    inspect_sr = df.iloc[-60:][(symbol, "Close")].copy()
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

        async with self.candle_data.write_lock as wrapper:
            inner = wrapper.inner
            for column_name, new_data_value in new_datas.items():
                inner.loc[before_moment, column_name] = new_data_value
            if not inner.index.is_monotonic_increasing:
                inner = inner.sort_index()

        duration = (datetime.now(timezone.utc) - current_moment).total_seconds()
        remember_task_durations.add("add_candle_data", duration)

    async def stop_filling_candle_data(self, *args, **kwargs):
        stop_flag.make("download_fill_candle_data")

    async def guide_donation(self, *args, **kwargs):
        formation = [
            "Support Solie",
            DonationGuide,
            True,
            None,
        ]
        await solie.window.overlap(formation)
