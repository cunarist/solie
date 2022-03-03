from datetime import datetime, timedelta, timezone
import os
import math
import threading
import time
import webbrowser
from collections import deque
import pickle
import itertools
import copy
import random
import logging

import pandas as pd
import numpy as np

from instrument.api_requester import ApiRequester
from instrument.api_streamer import ApiStreamer
from recipe import simply_format
from recipe import stop_flag
from recipe import check_internet
from recipe import process
from recipe import thread
from recipe import standardize
from recipe import download_aggtrade_data
from recipe import combine_candle_datas
from recipe import sort_dataframe
from recipe import fill_holes_with_aggtrades


class Collector:
    def __init__(self, root):

        # ■■■■■ 클래스 기초 ■■■■■

        self.root = root

        # ■■■■■ 데이터 관리 ■■■■■

        self.workerpath = standardize.get_datapath() + "/collector"
        os.makedirs(self.workerpath, exist_ok=True)
        self.datalocks = [threading.Lock() for _ in range(8)]

        # ■■■■■ 기억하고 표시 ■■■■■

        self.api_requester = ApiRequester()

        self.task_durations = {
            "add_candle_data": deque(maxlen=360),
            "add_book_tickers": deque(maxlen=1280),
            "add_mark_price": deque(maxlen=10),
            "add_aggregate_trades": deque(maxlen=1280),
        }

        self.exchange_state = {
            "minimum_notionals": {},
            "price_precisions": {},
            "quantity_precisions": {},
        }

        self.aggtrade_candle_sizes = {}
        for symbol in standardize.get_basics()["target_symbols"]:
            self.aggtrade_candle_sizes[symbol] = 0

        # 캔들 데이터
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

        # 실시간 데이터 뭉치들
        try:
            filepath = self.workerpath + "/realtime_data_chunks.pickle"
            with open(filepath, "rb") as file:
                self.realtime_data_chunks = copy.deepcopy(pickle.load(file))
        except FileNotFoundError:
            field_names = itertools.product(
                standardize.get_basics()["target_symbols"],
                ("Best Bid Price", "Best Ask Price", "Mark Price"),
            )
            field_names = [str(field_name) for field_name in field_names]
            dtype = [(field_name, np.float32) for field_name in field_names]
            dtpye = [("index", "datetime64[ns]")] + dtype
            self.realtime_data_chunks = [
                np.recarray(shape=(0,), dtype=dtpye) for _ in range(2)
            ]

        # 묶음 거래 (끊김 없는 정확한 파악이 중요하기 때문에 저장하고 읽는 대상이 아님)
        field_names = itertools.product(
            standardize.get_basics()["target_symbols"],
            ("Price", "Volume"),
        )
        field_names = [str(field_name) for field_name in field_names]
        dtype = [(field_name, np.float32) for field_name in field_names]
        dtpye = [("index", "datetime64[ns]")] + dtype
        self.aggregate_trades = np.recarray(shape=(0,), dtype=dtpye)

        # ■■■■■ 기본 실행 ■■■■■

        self.root.initialize_functions.append(
            lambda: self.get_exchange_information(),
        )
        self.root.finalize_functions.append(
            lambda: self.save_candle_data(),
        )
        self.root.finalize_functions.append(
            lambda: self.save_realtime_data_chunks(),
        )

        # ■■■■■ 반복 타이머 ■■■■■

        self.root.scheduler.add_job(
            self.display_information,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.fill_candle_data_holes,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.add_candle_data,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.organize_everything,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.get_exchange_information,
            trigger="cron",
            minute="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.save_realtime_data_chunks,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.save_candle_data,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )

        # ■■■■■ 웹소켓 스트리밍 ■■■■■

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

        # ■■■■■ 인터넷 연결 상태에 따라 ■■■■■

        connected_functrions = []
        check_internet.add_connected_functions(connected_functrions)

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

        # ■■■■■ 인터넷 연결 확인 ■■■■■

        if not check_internet.connected():
            return

        # ■■■■■ 단위에 맞춘 현재 시각 ■■■■■

        # 10초 단위로 내림하기
        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        split_moment = current_moment - timedelta(days=2)

        # ■■■■■ 지난 24시간 구멍 채우기 (앞쪽부터 순차적으로 10초마다) ■■■■■

        full_symbols = []
        request_count = 0

        # 최근 부분만 잘라내기
        with self.datalocks[0]:
            df = self.candle_data
            recent_candle_data = df[df.index >= split_moment].copy()

        target_symbols = standardize.get_basics()["target_symbols"]
        while len(full_symbols) < len(target_symbols) and request_count < 10:

            for symbol in target_symbols:

                if symbol in full_symbols:
                    continue

                recent_candle_data = process.apply(
                    sort_dataframe.do, recent_candle_data
                )

                from_moment = current_moment - timedelta(hours=24)
                until_moment = current_moment - timedelta(minutes=1)

                inspect_df = recent_candle_data[symbol][from_moment:until_moment]
                base_index = inspect_df.dropna().index
                temp_sr = pd.Series(0, index=base_index)
                written_moments = len(temp_sr)

                if written_moments == (86400 - 60) / 10 + 1:
                    # 구멍이 없는 경우 다음 심볼로
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

                # 데이터 요청
                aggtrades = {}
                last_fetched_time = moment_to_fill_from
                while last_fetched_time < moment_to_fill_from + timedelta(seconds=10):
                    # 최소한 10초 블럭 하나는 완전히 채운다는 마인드
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

                recent_candle_data = process.apply(
                    fill_holes_with_aggtrades.do,
                    symbol,
                    recent_candle_data,
                    aggtrades,
                    moment_to_fill_from,
                    last_fetched_time,
                )

        # 다시 합치기
        with self.datalocks[0]:
            df = self.candle_data
            original_candle_data = df[df.index < split_moment]
            # 그 사이 다른 데이터가 추가됐을 수도 있으니..
            temp_df = df[df.index >= split_moment]
            recent_candle_data = recent_candle_data.combine_first(temp_df)
            recent_candle_data = recent_candle_data.sort_index(axis="index")
            recent_candle_data = recent_candle_data.sort_index(axis="columns")
            candle_data = pd.concat([original_candle_data, recent_candle_data])
            self.candle_data = candle_data

    def display_information(self, *args, **kwargs):

        with self.datalocks[0]:
            if len(self.candle_data) == 0:
                # 처음 실행한 경우
                return

        if len(self.exchange_state["price_precisions"]) == 0:
            # 실행 직후
            return

        # 가격
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
                widget = self.root.price_labels[symbol]
                self.root.undertake(lambda w=widget, t=text: w.setText(t), False)

        # 하단 정보
        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        count_start_moment = current_moment - timedelta(hours=24)
        text = ""

        with self.datalocks[0]:
            df = self.candle_data
            first_written_moment = df.index[0]
            last_written_moment = df.index[-1]
            cumulated_moments = len(df[count_start_moment:].dropna())
        needed_moments = 24 * 60 * 60 / 10
        ratio = cumulated_moments / needed_moments

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
        written_length_text = f"{range_days}일 {range_hours}시간 {range_minutes}분"

        text += f"캔들 데이터 시작 {first_written_moment}"
        text += "  ⦁  "
        text += f"캔들 데이터 끝 {last_written_moment}"
        text += "  ⦁  "
        text += f"지난 24시간 캔들 데이터 누적률 {round(ratio * 100, 2)}%"
        text += "  ⦁  "
        text += f"실시간 데이터 길이 {written_length_text}"

        self.root.undertake(lambda t=text: self.root.label_6.setText(t), False)

    def open_binance_data_page(self, *args, **kwargs):
        webbrowser.open("https://www.binance.com/en/landing/data")

    def save_candle_data(self, *args, **kwargs):

        # ■■■■■ 변수 마련 ■■■■■

        current_year = datetime.now(timezone.utc).year
        filepath = f"{self.workerpath}/candle_data_{current_year}.pickle"

        with self.datalocks[0]:
            df = self.candle_data
            year_df = df[df.index.year == current_year].copy()

        # ■■■■■ 새 파일 만들기 ■■■■■

        year_df.to_pickle(filepath + ".new")

        # ■■■■■ 용량 확인 후 원래 파일 백업하고 대체 ■■■■■

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

    def save_realtime_data_chunks(self, *args, **kwargs):

        with self.datalocks[1]:
            realtime_data_chunks = copy.deepcopy(self.realtime_data_chunks)

        filepath = f"{self.workerpath}/realtime_data_chunks.pickle"
        with open(filepath, "wb") as file:
            pickle.dump(realtime_data_chunks, file)

    def save_all_years_history(self, *args, **kwargs):

        # 가격 데이터
        with self.datalocks[0]:
            years_sr = self.candle_data.index.year.drop_duplicates()
        years = years_sr.tolist()

        for year in years:
            with self.datalocks[0]:
                df = self.candle_data
                year_df = df[df.index.year == year].copy()
            filepath = f"{self.workerpath}/candle_data_{year}.pickle"
            year_df.to_pickle(filepath)

    def download_fill_history(self, *args, **kwargs):

        # ■■■■■ 의사 확인 ■■■■■

        target = args[0]

        if target == "until_last_month":
            question = [
                "지난 달까지의 캔들 데이터를 채우시겠어요?",
                "바이낸스가 제공하는 2020년 1월부터 지난 달까지의 데이터를 받아 기록하게 됩니다. 대용량 데이터를 다운로드하기 때문에"
                " 인터넷 속도에 따라 걸리는 시간이 달라집니다. 짧게는 수십 분, 길게는 몇 시간이 걸릴 수 있습니다. 바이낸스에 데이터가"
                " 아직 등록되지 않은 경우에는 건너뜁니다.",
                ["아니오", "예"],
            ]
        elif target == "this_month":
            question = [
                "이번 달의 캔들 데이터를 채우시겠어요?",
                "이번 달 1일부터의 어제까지의 데이터를 바이낸스에서 받아 기록하게 됩니다. 대용량 데이터를 다운로드하기 때문에 인터넷 속도에"
                " 따라 걸리는 시간이 달라집니다. 몇 분이 걸릴 수 있습니다. 바이낸스에 데이터가 아직 등록되지 않은 경우에는 건너뜁니다.",
                ["아니오", "예"],
            ]
        elif target == "last_two_days":
            question = [
                "어제와 그저께의 캔들 데이터를 채우시겠어요?",
                "어제와 그저께의 데이터를 바이낸스에서 받아 기록하게 됩니다. 바이낸스에 데이터가 아직 등록되지 않은 경우에는 건너뜁니다.",
                ["아니오", "예"],
            ]

        answer = self.root.ask(question)
        if answer in (0, 1):
            return

        # ■■■■■ 목록 준비 ■■■■■

        task_id = stop_flag.make("download_fill_history")

        target_symbols = standardize.get_basics()["target_symbols"]
        if target == "until_last_month":
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            target_tuples = []
            for year in range(2020, current_year + 1):
                if year == current_year:
                    final_month = current_month - 1
                else:
                    final_month = 12
                for month in range(1, final_month + 1):
                    for symbol in target_symbols:
                        target_tuples.append(
                            (
                                symbol,
                                "monthly",
                                year,
                                month,
                            )
                        )
        elif target == "this_month":
            current_year = datetime.now(timezone.utc).year
            current_month = datetime.now(timezone.utc).month
            current_day = datetime.now(timezone.utc).day
            target_tuples = []
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
        elif target == "last_two_days":
            now = datetime.now(timezone.utc)
            yesterday = now - timedelta(hours=24)
            day_before_yesterday = yesterday - timedelta(hours=24)
            target_tuples = []
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

        # ■■■■■ 진행 막대 재생 ■■■■■

        def job():
            while True:
                if stop_flag.find("download_fill_history", task_id):
                    widget = self.root.progressBar_3
                    self.root.undertake(lambda w=widget: w.setValue(0), False)
                    return
                else:
                    if done_steps == total_steps:
                        progressbar_value = self.root.undertake(
                            lambda: self.root.progressBar_3.value(), True
                        )
                        if progressbar_value == 1000:
                            time.sleep(0.1)
                            widget = self.root.progressBar_3
                            self.root.undertake(lambda w=widget: w.setValue(0), False)
                            return
                    widget = self.root.progressBar_3
                    before_value = self.root.undertake(lambda w=widget: w.value(), True)
                    if before_value < 1000:
                        remaining = (
                            math.ceil(1000 / total_steps * done_steps) - before_value
                        )
                        new_value = before_value + math.ceil(remaining * 0.2)
                        self.root.undertake(
                            lambda w=widget, v=new_value: w.setValue(v), False
                        )
                    time.sleep(0.01)

        thread.apply_async(job)

        # ■■■■■ 병렬 처리 ■■■■■

        random.shuffle(target_tuples)
        lanes = process.get_pool_process_count()
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
                if stop_flag.find("download_fill_history", task_id):
                    return
                returned = process.apply(download_aggtrade_data.do, target_tuple)
                if returned is not None:
                    new_df = returned
                    with combined_df_lock:
                        combined_df = process.apply(
                            combine_candle_datas.do,
                            new_df,
                            combined_df,
                        )
                done_steps += 1

        thread.map(job, target_tuple_chunks)

        if stop_flag.find("download_fill_history", task_id):
            return

        # ■■■■■ 원래 있던 것과 합치고 정리하기 ■■■■■

        with self.datalocks[0]:

            df = process.apply(combine_candle_datas.do, combined_df, self.candle_data)
            self.candle_data = df

        # ■■■■■ 저장 ■■■■■

        self.save_all_years_history()

        # ■■■■■ 알림 ■■■■■

        text = "바이낸스 과거 데이터를 다운로드해서 캔들 데이터를 채웠습니다."
        logger = logging.getLogger("solsol")
        logger.info(text)

        # ■■■■■ 표시 ■■■■■

        self.root.transactor.display_lines()
        self.root.simulator.display_lines()

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
        self.task_durations["add_book_tickers"].append(duration)

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
        self.task_durations["add_mark_price"].append(duration)

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
        self.task_durations["add_aggregate_trades"].append(duration)

    def organize_everything(self, *args, **kwargs):

        with self.datalocks[1]:
            self.realtime_data_chunks[-1].sort(order="index")
            if len(self.realtime_data_chunks[-1]) > 2**16:
                new_chunk = self.realtime_data_chunks[-1][0:0].copy()
                self.realtime_data_chunks.append(new_chunk)
                del new_chunk
            if len(self.realtime_data_chunks) > 64:
                self.realtime_data_chunks.pop(0)

        with self.datalocks[2]:
            self.aggregate_trades.sort(order="index")
            last_index = self.aggregate_trades[-1]["index"]
            slice_from = last_index - np.timedelta64(60, "s")
            mask = self.aggregate_trades["index"] > slice_from
            self.aggregate_trades = self.aggregate_trades[mask].copy()

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
        self.task_durations["add_candle_data"].append(duration)

    def download_fill_history_until_last_month(self, *args, **kwargs):

        self.download_fill_history("until_last_month")

    def download_fill_history_this_month(self, *args, **kwargs):

        self.download_fill_history("this_month")

    def download_fill_history_last_two_days(self, *args, **kwargs):

        self.download_fill_history("last_two_days")
