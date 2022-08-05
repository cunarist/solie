from datetime import datetime, timedelta, timezone
import os
import math
import threading
import time
import webbrowser
from collections import deque
import itertools
import random
import logging

import pandas as pd
import numpy as np

from module import core
from module import process_toss
from module import thread_toss
from module.instrument.api_requester import ApiRequester
from module.instrument.api_streamer import ApiStreamer
from module.recipe import simply_format
from module.recipe import stop_flag
from module.recipe import check_internet
from module.recipe import standardize
from module.recipe import download_aggtrade_data
from module.recipe import combine_candle_datas
from module.recipe import sort_dataframe
from module.recipe import fill_holes_with_aggtrades
from module.recipe import remember_task_durations


class Collector:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = standardize.get_datapath() + "/collector"
        os.makedirs(self.workerpath, exist_ok=True)
        self.datalocks = [threading.Lock() for _ in range(8)]

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.exchange_state = {
            "maximum_quantities": {},
            "minimum_notionals": {},
            "price_precisions": {},
            "quantity_precisions": {},
        }

        self.aggtrade_candle_sizes = {}
        for symbol in standardize.get_basics()["target_symbols"]:
            self.aggtrade_candle_sizes[symbol] = 0

        # candle data
        self.candle_data = pd.DataFrame(
            columns=pd.MultiIndex.from_product(
                [
                    standardize.get_basics()["target_symbols"],
                    ("Open", "High", "Low", "Close", "Volume"),
                ]
            ),
            dtype=np.float32,
            index=pd.DatetimeIndex([], tz="UTC"),
        )
        years = [
            int(simply_format.numeric(filename))
            for filename in os.listdir(self.workerpath)
            if filename.startswith("candle_data_") and filename.endswith(".pickle")
        ]
        divided_datas = [self.candle_data]
        for year in years:
            filepath = f"{self.workerpath}/candle_data_{year}.pickle"
            more_df = pd.read_pickle(filepath)
            divided_datas.append(more_df)
        self.candle_data = pd.concat(divided_datas)
        self.candle_data = self.candle_data[~self.candle_data.index.duplicated()]
        self.candle_data = self.candle_data.sort_index(axis="index")
        self.candle_data = self.candle_data.sort_index(axis="columns")
        self.candle_data = self.candle_data.asfreq("10S")
        self.candle_data = self.candle_data.astype(np.float32)

        # realtime data chunks
        field_names = itertools.product(
            standardize.get_basics()["target_symbols"],
            ("Best Bid Price", "Best Ask Price", "Mark Price"),
        )
        field_names = [str(field_name) for field_name in field_names]
        dtype = [(field_name, np.float32) for field_name in field_names]
        dtpye = [("index", "datetime64[ns]")] + dtype
        self.realtime_data_chunks = deque(
            [np.recarray(shape=(0,), dtype=dtpye) for _ in range(2)], maxlen=64
        )

        # aggregate trades
        field_names = itertools.product(
            standardize.get_basics()["target_symbols"],
            ("Price", "Volume"),
        )
        field_names = [str(field_name) for field_name in field_names]
        dtype = [(field_name, np.float32) for field_name in field_names]
        dtpye = [("index", "datetime64[ns]")] + dtype
        self.aggregate_trades = np.recarray(shape=(0,), dtype=dtpye)

        # ■■■■■ default executions ■■■■■

        core.window.initialize_functions.append(
            lambda: self.get_exchange_information(),
        )
        core.window.finalize_functions.append(
            lambda: self.save_candle_data(),
        )

        # ■■■■■ repetitive schedules ■■■■■

        core.window.scheduler.add_job(
            self.display_information,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.fill_candle_data_holes,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.add_candle_data,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.organize_everything,
            trigger="cron",
            minute="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.get_exchange_information,
            trigger="cron",
            minute="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.save_candle_data,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = [
            ApiStreamer(
                "wss://fstream.binance.com/ws/!markPrice@arr@1s",
                self.add_mark_price,
            ),
        ]
        for symbol in standardize.get_basics()["target_symbols"]:
            api_streamer = ApiStreamer(
                f"wss://fstream.binance.com/ws/{symbol.lower()}@bookTicker",
                self.add_book_tickers,
            )
            self.api_streamers.append(api_streamer)
            api_streamer = ApiStreamer(
                f"wss://fstream.binance.com/ws/{symbol.lower()}@aggTrade",
                self.add_aggregate_trades,
            )
            self.api_streamers.append(api_streamer)

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functions = []
        check_internet.add_connected_functions(connected_functions)

        disconnected_functions = [
            lambda: self.clear_aggregate_trades(),
        ]
        check_internet.add_disconnected_functions(disconnected_functions)

    def get_exchange_information(self, *args, **kwargs):
        if not check_internet.connected():
            return

        payload = {}
        response = self.api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload=payload,
        )
        about_exchange = response

        for about_symbol in about_exchange["symbols"]:
            symbol = about_symbol["symbol"]

            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "MIN_NOTIONAL":
                    break
            minimum_notional = float(about_filter["notional"])
            self.exchange_state["minimum_notionals"][symbol] = minimum_notional

            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "LOT_SIZE":
                    break
            maximum_quantity = float(about_filter["maxQty"])
            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "MARKET_LOT_SIZE":
                    break
            maximum_quantity = min(maximum_quantity, float(about_filter["maxQty"]))
            self.exchange_state["maximum_quantities"][symbol] = maximum_quantity

            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "PRICE_FILTER":
                    break
            ticksize = float(about_filter["tickSize"])
            price_precision = int(math.log10(1 / ticksize))
            self.exchange_state["price_precisions"][symbol] = price_precision

            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "LOT_SIZE":
                    break
            stepsize = float(about_filter["stepSize"])
            quantity_precision = int(math.log10(1 / stepsize))
            self.exchange_state["quantity_precisions"][symbol] = quantity_precision

    def fill_candle_data_holes(self, *args, **kwargs):
        # ■■■■■ check internet connection ■■■■■

        if not check_internet.connected():
            return

        # ■■■■■ moments ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        split_moment = current_moment - timedelta(days=2)

        # ■■■■■ fill holes ■■■■■

        full_symbols = []
        request_count = 0

        # only the recent part
        with self.datalocks[0]:
            df = self.candle_data
            recent_candle_data = df[df.index >= split_moment].copy()

        target_symbols = standardize.get_basics()["target_symbols"]
        while len(full_symbols) < len(target_symbols) and request_count < 10:
            for symbol in target_symbols:
                if symbol in full_symbols:
                    continue

                recent_candle_data = process_toss.apply(
                    sort_dataframe.do, recent_candle_data
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
                moment_to_fill_from = nan_index[0]

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
                    response = self.api_requester.binance(
                        http_method="GET",
                        path="/fapi/v1/aggTrades",
                        payload=payload,
                    )
                    request_count += 1
                    for aggtrade in response:
                        aggtrade_id = aggtrade["a"]
                        aggtrades[aggtrade_id] = aggtrade
                    last_fetched_id = max(aggtrades.keys())
                    last_fetched_time = datetime.fromtimestamp(
                        aggtrades[last_fetched_id]["T"] / 1000, tz=timezone.utc
                    )

                recent_candle_data = process_toss.apply(
                    fill_holes_with_aggtrades.do,
                    symbol,
                    recent_candle_data,
                    aggtrades,
                    moment_to_fill_from,
                    last_fetched_time,
                )

        # combine
        with self.datalocks[0]:
            df = self.candle_data
            original_candle_data = df[df.index < split_moment]
            # in case the other data is added during the task
            # read the data again
            temp_df = df[df.index >= split_moment]
            recent_candle_data = recent_candle_data.combine_first(temp_df)
            recent_candle_data = recent_candle_data.sort_index(axis="index")
            recent_candle_data = recent_candle_data.sort_index(axis="columns")
            candle_data = pd.concat([original_candle_data, recent_candle_data])
            self.candle_data = candle_data

    def display_information(self, *args, **kwargs):
        with self.datalocks[0]:
            if len(self.candle_data) == 0:
                # when the app is executed for the first time
                return

        if len(self.exchange_state["price_precisions"]) == 0:
            # right after the app execution
            return

        # price
        with self.datalocks[2]:
            ar = self.aggregate_trades.copy()
        price_precisions = self.exchange_state["price_precisions"]

        for symbol in standardize.get_basics()["target_symbols"]:
            temp_ar = ar[str((symbol, "Price"))]
            temp_ar = temp_ar[temp_ar != 0]
            if len(temp_ar) > 0:
                price_precision = price_precisions[symbol]
                latest_price = temp_ar[-1]
                text = "＄" + str(round(latest_price, price_precision))
                widget = core.window.price_labels[symbol]
                core.window.undertake(lambda w=widget, t=text: w.setText(t), False)

        # bottom information
        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        count_start_moment = current_moment - timedelta(hours=24)

        # add one to ignore temporarily missing candle
        with self.datalocks[0]:
            df = self.candle_data
            cumulated_moments = len(df[count_start_moment:].dropna())
        needed_moments = 24 * 60 * 60 / 10
        ratio = min(float(1), (cumulated_moments + 1) / needed_moments)

        chunk_count = len(self.realtime_data_chunks)
        first_written_time = None
        last_written_time = None
        for turn in range(chunk_count):
            with self.datalocks[1]:
                if len(self.realtime_data_chunks[turn]) > 0:
                    if first_written_time is None:
                        first_record = self.realtime_data_chunks[turn][0]
                        first_written_time = first_record["index"]
                        del first_record
                    last_record = self.realtime_data_chunks[turn][-1]
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
        text += f"24h candle data accumulation rate {round(ratio * 100, 2)}%"
        text += "  ⦁  "
        text += f"Realtime data length {written_length_text}"

        core.window.undertake(lambda t=text: core.window.label_6.setText(t), False)

    def open_binance_data_page(self, *args, **kwargs):
        webbrowser.open("https://www.binance.com/en/landing/data")

    def save_candle_data(self, *args, **kwargs):
        # ■■■■■ default values ■■■■■

        current_year = datetime.now(timezone.utc).year
        filepath = f"{self.workerpath}/candle_data_{current_year}.pickle"

        with self.datalocks[0]:
            df = self.candle_data
            year_df = df[df.index.year == current_year].copy()

        # ■■■■■ make a new file ■■■■■

        year_df.to_pickle(filepath + ".new")

        # ■■■■■ safely replace the existing file ■■■■■

        try:
            new_size = os.path.getsize(filepath + ".new")
        except FileNotFoundError:
            new_size = 0

        try:
            original_size = os.path.getsize(filepath)
        except FileNotFoundError:
            original_size = 0

        try:
            backup_size = os.path.getsize(filepath + ".backup")
        except FileNotFoundError:
            backup_size = 0

        if backup_size <= original_size and original_size <= new_size:
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
        elif original_size <= new_size:
            try:
                os.remove(filepath)
            except FileNotFoundError:
                pass

    def save_all_years_history(self, *args, **kwargs):
        with self.datalocks[0]:
            years_sr = self.candle_data.index.year.drop_duplicates()
        years = years_sr.tolist()

        for year in years:
            with self.datalocks[0]:
                df = self.candle_data
                year_df = df[df.index.year == year].copy()
            filepath = f"{self.workerpath}/candle_data_{year}.pickle"
            year_df.to_pickle(filepath)

    def download_fill_candle_data(self, *args, **kwargs):
        # ■■■■■ ask filling type ■■■■■

        question = [
            "Choose the range to fill",
            "Solsol will fill the candle data with historical data provided by Binacne."
            " The more you fill, the longer it takes. Amount of a few days only takes"
            " few minutes while amount of a few years can take hours.",
            [
                "From 2020 to last year",
                "From first month of this year to last month",
                "This month",
                "Yesterday and the day before yesterday",
            ],
            True,
        ]
        answer = core.window.ask(question)
        if answer in (0,):
            return

        filling_type = answer

        # ■■■■■ prepare target tuples for downloading ■■■■■

        task_id = stop_flag.make("download_fill_candle_data")

        target_tuples = []
        target_symbols = standardize.get_basics()["target_symbols"]
        if filling_type == 1:
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
        elif filling_type == 3:
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
        elif filling_type == 4:
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

        def job():
            while True:
                if stop_flag.find("download_fill_candle_data", task_id):
                    widget = core.window.progressBar_3
                    core.window.undertake(lambda w=widget: w.setValue(0), False)
                    return
                else:
                    if done_steps == total_steps:
                        progressbar_value = core.window.undertake(
                            lambda: core.window.progressBar_3.value(), True
                        )
                        if progressbar_value == 1000:
                            time.sleep(0.1)
                            widget = core.window.progressBar_3
                            core.window.undertake(lambda w=widget: w.setValue(0), False)
                            return
                    widget = core.window.progressBar_3
                    before_value = core.window.undertake(
                        lambda w=widget: w.value(), True
                    )
                    if before_value < 1000:
                        remaining = (
                            math.ceil(1000 / total_steps * done_steps) - before_value
                        )
                        new_value = before_value + math.ceil(remaining * 0.2)
                        core.window.undertake(
                            lambda w=widget, v=new_value: w.setValue(v), False
                        )
                    time.sleep(0.01)

        thread_toss.apply_async(job)

        # ■■■■■ calculate in parellel ■■■■■

        random.shuffle(target_tuples)
        lanes = process_toss.get_pool_process_count()
        chunk_size = math.ceil(len(target_tuples) / lanes)
        target_tuple_chunks = []
        for turn in range(lanes):
            new_chunk = target_tuples[turn * chunk_size : (turn + 1) * chunk_size]
            target_tuple_chunks.append(new_chunk)

        combined_df_lock = threading.Lock()

        with self.datalocks[0]:
            combined_df = self.candle_data.iloc[0:0].copy()

        def job(target_tuple_chunk):
            nonlocal done_steps
            nonlocal combined_df

            for target_tuple in target_tuple_chunk:
                if stop_flag.find("download_fill_candle_data", task_id):
                    return
                returned = process_toss.apply(download_aggtrade_data.do, target_tuple)
                if returned is not None:
                    new_df = returned
                    with combined_df_lock:
                        combined_df = process_toss.apply(
                            combine_candle_datas.do,
                            new_df,
                            combined_df,
                        )
                done_steps += 1

        thread_toss.map(job, target_tuple_chunks)

        if stop_flag.find("download_fill_candle_data", task_id):
            return

        # ■■■■■ combine ■■■■■

        with self.datalocks[0]:
            df = process_toss.apply(
                combine_candle_datas.do, combined_df, self.candle_data
            )
            self.candle_data = df

        # ■■■■■ save ■■■■■

        self.save_all_years_history()

        # ■■■■■ add to log ■■■■■

        text = "Filled the candle data with the history data downloaded from Binance"
        logger = logging.getLogger("solsol")
        logger.info(text)

        # ■■■■■ display to graphs ■■■■■

        core.window.transactor.display_lines()
        core.window.simulator.display_lines()

    def add_book_tickers(self, *args, **kwargs):
        received = kwargs.get("received")
        start_time = datetime.now(timezone.utc)
        symbol = received["s"]
        best_bid = received["b"]
        best_ask = received["a"]
        event_time = np.datetime64(received["E"] * 10**6, "ns")
        with self.datalocks[1]:
            original_size = self.realtime_data_chunks[-1].shape[0]
            self.realtime_data_chunks[-1].resize(original_size + 1)
            self.realtime_data_chunks[-1][-1]["index"] = event_time
            find_key = str((symbol, "Best Bid Price"))
            self.realtime_data_chunks[-1][-1][find_key] = best_bid
            find_key = str((symbol, "Best Ask Price"))
            self.realtime_data_chunks[-1][-1][find_key] = best_ask
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        remember_task_durations.add("add_book_tickers", duration)

    def add_mark_price(self, *args, **kwargs):
        received = kwargs.get("received")
        start_time = datetime.now(timezone.utc)
        target_symbols = standardize.get_basics()["target_symbols"]
        event_time = np.datetime64(received[0]["E"] * 10**6, "ns")
        filtered_data = {}
        for about_mark_price in received:
            symbol = about_mark_price["s"]
            if symbol in target_symbols:
                mark_price = float(about_mark_price["p"])
                filtered_data[symbol] = mark_price
        with self.datalocks[1]:
            original_size = self.realtime_data_chunks[-1].shape[0]
            self.realtime_data_chunks[-1].resize(original_size + 1)
            self.realtime_data_chunks[-1][-1]["index"] = event_time
            for symbol, mark_price in filtered_data.items():
                find_key = str((symbol, "Mark Price"))
                self.realtime_data_chunks[-1][-1][find_key] = mark_price
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        remember_task_durations.add("add_mark_price", duration)

    def add_aggregate_trades(self, *args, **kwargs):
        received = kwargs.get("received")
        start_time = datetime.now(timezone.utc)
        symbol = received["s"]
        price = float(received["p"])
        volume = float(received["q"])
        trade_time = np.datetime64(received["T"] * 10**6, "ns")
        with self.datalocks[2]:
            original_size = self.aggregate_trades.shape[0]
            self.aggregate_trades.resize(original_size + 1)
            self.aggregate_trades[-1]["index"] = trade_time
            self.aggregate_trades[-1][str((symbol, "Price"))] = price
            self.aggregate_trades[-1][str((symbol, "Volume"))] = volume
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        remember_task_durations.add("add_aggregate_trades", duration)

    def organize_everything(self, *args, **kwargs):
        start_time = datetime.now(timezone.utc)

        with self.datalocks[0]:
            self.candle_data = self.candle_data.asfreq("10S")
            self.candle_data = self.candle_data.astype(np.float32)

        with self.datalocks[1]:
            self.realtime_data_chunks[-1].sort(order="index")
            if len(self.realtime_data_chunks[-1]) > 2**16:
                new_chunk = self.realtime_data_chunks[-1][0:0].copy()
                self.realtime_data_chunks.append(new_chunk)
                del new_chunk

        with self.datalocks[2]:
            self.aggregate_trades.sort(order="index")
            last_index = self.aggregate_trades[-1]["index"]
            slice_from = last_index - np.timedelta64(60, "s")
            mask = self.aggregate_trades["index"] > slice_from
            self.aggregate_trades = self.aggregate_trades[mask].copy()

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        remember_task_durations.add("organize_everything", duration)

    def clear_aggregate_trades(self, *args, **kwargs):
        with self.datalocks[2]:
            self.aggregate_trades = self.aggregate_trades[0:0].copy()

    def add_candle_data(self, *args, **kwargs):
        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        with self.datalocks[2]:
            data_length = len(self.aggregate_trades)
        if data_length == 0:
            return

        for _ in range(20):
            with self.datalocks[2]:
                last_received_index = self.aggregate_trades[-1]["index"]
            if np.datetime64(current_moment) < last_received_index:
                break
            time.sleep(0.1)

        with self.datalocks[2]:
            aggregate_trades = self.aggregate_trades.copy()

        first_received_index = aggregate_trades[0]["index"]
        if first_received_index >= np.datetime64(before_moment):
            return

        new_datas = {}

        for symbol in standardize.get_basics()["target_symbols"]:
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
                with self.datalocks[0]:
                    df = self.candle_data
                    inspect_sr = df.iloc[-60:][(symbol, "Close")].copy()
                last_price = inspect_sr.dropna().tolist()[-1]
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

        with self.datalocks[0]:
            for column_name, new_data_value in new_datas.items():
                self.candle_data.loc[before_moment, column_name] = new_data_value

        duration = (datetime.now(timezone.utc) - current_moment).total_seconds()
        remember_task_durations.add("add_candle_data", duration)

    def stop_filling_candle_data(self, *args, **kwargs):
        stop_flag.make("download_fill_candle_data")
