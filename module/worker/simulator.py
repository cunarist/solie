from datetime import datetime, timedelta, timezone
import math
import threading
import multiprocessing
import os
import time
import re
import pickle
import copy

from PyQt6 import QtCore
import pandas as pd
import numpy as np
from scipy.signal import find_peaks

from module.recipe import simulate_unit
from module.recipe import make_indicators
from module.recipe import stop_flag
from module.recipe import check_internet
from module.recipe import digitize
from module.recipe import process_toss
from module.recipe import thread_toss
from module.recipe import standardize


class Simulator:
    def __init__(self, root):

        # ■■■■■ the basic ■■■■■

        self.root = root

        # ■■■■■ for data management ■■■■■

        self.workerpath = standardize.get_datapath() + "/simulator"
        os.makedirs(self.workerpath, exist_ok=True)
        self.datalocks = [threading.Lock() for _ in range(8)]

        # ■■■■■ remember and display ■■■■■

        self.viewing_symbol = standardize.get_basics()["target_symbols"][0]

        self.about_viewing = None

        self.calculation_settings = {
            "year": datetime.now(timezone.utc).year,
            "strategy": 0,
        }
        self.presentation_settings = {
            "maker_fee": 0.02,
            "taker_fee": 0.04,
            "leverage": 1,
        }

        self.raw_account_state = {
            "observed_until": datetime.now(timezone.utc),
            "wallet_balance": 1,
            "positions": {},
            "open_orders": {},
        }
        for symbol in standardize.get_basics()["target_symbols"]:
            self.raw_account_state["positions"][symbol] = {
                "margin": 0,
                "direction": "none",
                "entry_price": 0,
                "update_time": datetime.fromtimestamp(0, tz=timezone.utc),
            }
            self.raw_account_state["open_orders"][symbol] = {}
        self.raw_scribbles = {}
        self.raw_asset_record = pd.DataFrame(
            columns=[
                "Cause",
                "Symbol",
                "Side",
                "Fill Price",
                "Role",
                "Margin Ratio",
                "Order ID",
                "Result Asset",
            ],
            index=pd.DatetimeIndex([], tz="UTC"),
        )
        self.raw_unrealized_changes = pd.Series(
            index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32
        )

        self.account_state = {
            "observed_until": datetime.now(timezone.utc),
            "wallet_balance": 1,
            "positions": {},
            "open_orders": {},
        }
        for symbol in standardize.get_basics()["target_symbols"]:
            self.account_state["positions"][symbol] = {
                "margin": 0,
                "direction": "none",
                "entry_price": 0,
                "update_time": datetime.fromtimestamp(0, tz=timezone.utc),
            }
            self.account_state["open_orders"][symbol] = {}
        self.scribbles = {}
        self.asset_record = pd.DataFrame(
            columns=[
                "Cause",
                "Symbol",
                "Side",
                "Fill Price",
                "Role",
                "Margin Ratio",
                "Order ID",
                "Result Asset",
            ],
            index=pd.DatetimeIndex([], tz="UTC"),
        )
        self.unrealized_changes = pd.Series(
            index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32
        )

        text = "아무 전략도 그려져 있지 않음"
        self.root.undertake(lambda t=text: self.root.label_19.setText(t), False)

        # ■■■■■ default executions ■■■■■

        self.root.initialize_functions.append(
            lambda: self.display_lines(),
        )
        self.root.initialize_functions.append(
            lambda: self.display_year_range(),
        )

        # ■■■■■ repetitive schedules ■■■■■

        self.root.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            minute="*",
            executor="thread_pool_executor",
            kwargs={"only_light_lines": True},
        )
        self.root.scheduler.add_job(
            self.display_available_years,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
            kwargs={"periodic": True},
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = []

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functrions = []
        check_internet.add_connected_functions(connected_functrions)

        disconnected_functions = []
        check_internet.add_disconnected_functions(disconnected_functions)

    def update_viewing_symbol(self, *args, **kwargs):
        def job():
            return self.root.comboBox_6.currentText()

        alias = self.root.undertake(job, True)
        symbol = self.root.alias_to_symbol[alias]
        self.viewing_symbol = symbol

        self.display_lines()

    def update_calculation_settings(self, *args, **kwargs):

        text = self.root.undertake(lambda: self.root.comboBox_5.currentText(), True)
        self.calculation_settings["year"] = int(text)

        index = self.root.undertake(lambda: self.root.comboBox.currentIndex(), True)
        strategy = self.root.strategy_tuples[index][0]
        self.calculation_settings["strategy"] = strategy

        if strategy == 0:
            strategy_details = self.root.strategist.details
        else:
            for strategy_tuple in self.root.strategy_tuples:
                if strategy_tuple[0] == strategy:
                    strategy_details = strategy_tuple[2]
        is_working_strategy = strategy_details[0]

        if not is_working_strategy:
            question = [
                "사용 가능 전략이 아닙니다.",
                "이 전략으로는 시뮬레이션 계산을 할 수 없습니다.",
                ["확인"],
                False,
            ]
            self.root.ask(question)

        self.display_lines()

    def update_presentation_settings(self, *args, **kwargs):
        widget = self.root.spinBox_2
        input_value = self.root.undertake(lambda w=widget: w.value(), True)
        self.presentation_settings["leverage"] = input_value
        widget = self.root.doubleSpinBox
        input_value = self.root.undertake(lambda w=widget: w.value(), True)
        self.presentation_settings["taker_fee"] = input_value
        widget = self.root.doubleSpinBox_2
        input_value = self.root.undertake(lambda w=widget: w.value(), True)
        self.presentation_settings["maker_fee"] = input_value
        self.present()

    def display_lines(self, *args, **kwargs):

        periodic = kwargs.get("periodic", False)
        only_light_lines = kwargs.get("only_light_lines", False)

        if not only_light_lines:
            task_id = stop_flag.make("display_simulation_lines")

        # ■■■■■ check if the data exists ■■■■■

        with self.root.collector.datalocks[0]:
            if len(self.root.collector.candle_data) == 0:
                return

        # ■■■■■ moment ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        # ■■■■■ wait for the latest data to be added ■■■■■

        if periodic:
            for _ in range(50):
                if not only_light_lines:
                    if stop_flag.find("display_simulation_lines", task_id):
                        return
                with self.root.collector.datalocks[0]:
                    last_index = self.root.collector.candle_data.index[-1]
                    if last_index == before_moment:
                        break
                time.sleep(0.1)

        # ■■■■■ check strategy ■■■■■

        strategy = self.calculation_settings["strategy"]

        if strategy == 0:
            strategy_details = self.root.strategist.details
        else:
            for strategy_tuple in self.root.strategy_tuples:
                if strategy_tuple[0] == strategy:
                    strategy_details = strategy_tuple[2]
        is_fast_strategy = strategy_details[3]

        # ■■■■■ get the data ■■■■■

        symbol = self.viewing_symbol
        year = self.calculation_settings["year"]
        slice_until = datetime.now(timezone.utc)
        slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
        slice_until -= timedelta(seconds=1)

        if not only_light_lines:
            if is_fast_strategy:
                candle_data = pd.DataFrame(
                    columns=pd.MultiIndex.from_product(
                        [
                            standardize.get_basics()["target_symbols"],
                            ("Open", "High", "Low", "Close", "Volume"),
                        ]
                    ),
                    dtype=np.float32,
                    index=pd.DatetimeIndex([], tz="UTC"),
                )
            else:
                with self.root.collector.datalocks[0]:
                    df = self.root.collector.candle_data
                    mask = df.index.year == year
                    df = df[mask][:slice_until][[symbol]].copy()
                    candle_data = df

        with self.root.collector.datalocks[1]:
            original_chunks = self.root.collector.realtime_data_chunks
            realtime_data_chunks = copy.deepcopy(original_chunks)
        realtime_data = np.concatenate(realtime_data_chunks)
        with self.root.collector.datalocks[2]:
            aggregate_trades = self.root.collector.aggregate_trades.copy()

        with self.datalocks[0]:
            unrealized_changes = self.unrealized_changes.copy()
        with self.datalocks[1]:
            asset_record = self.asset_record.copy()

        # ■■■■■ make indicators ■■■■■

        indicators_script = self.root.strategist.indicators_script
        compiled_indicators_script = compile(indicators_script, "<string>", "exec")

        if is_fast_strategy:
            observed_data = process_toss.apply(digitize.do, realtime_data)
            indicators = process_toss.apply(
                make_indicators.do,
                observed_data=observed_data,
                strategy=strategy,
                compiled_custom_script=compiled_indicators_script,
            )

        else:
            if not only_light_lines:
                indicators = process_toss.apply(
                    make_indicators.do,
                    observed_data=candle_data,
                    strategy=strategy,
                    compiled_custom_script=compiled_indicators_script,
                )

        # ■■■■■ add the right end ■■■■■

        if not only_light_lines:
            if len(candle_data) > 0:
                last_written_moment = candle_data.index[-1]
                new_moment = last_written_moment + timedelta(seconds=10)
                new_index = candle_data.index.union([new_moment])
                candle_data = candle_data.reindex(new_index)

        observed_until = self.account_state["observed_until"]
        if len(asset_record) > 0:
            final_index = asset_record.index[-1]
            final_asset = asset_record.loc[final_index, "Result Asset"]
            asset_record.loc[observed_until, "Cause"] = "other"
            asset_record.loc[observed_until, "Result Asset"] = final_asset

        # ■■■■■ draw ■■■■■

        # mark price
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            data_x = realtime_data["index"].astype(np.int64) / 10**9
            data_y = realtime_data[str((symbol, "Mark Price"))]
            mask = data_y != 0
            data_y = data_y[mask]
            data_x = data_x[mask]
            widget = self.root.simulation_lines["mark_price"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # last price
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            data_x = aggregate_trades["index"].astype(np.int64) / 10**9
            data_y = aggregate_trades[str((symbol, "Price"))]
            mask = data_y != 0
            data_y = data_y[mask]
            data_x = data_x[mask]
            widget = self.root.simulation_lines["last_price"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # last trade volume
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            index_ar = aggregate_trades["index"].astype(np.int64) / 10**9
            value_ar = aggregate_trades[str((symbol, "Volume"))]
            mask = value_ar != 0
            index_ar = index_ar[mask]
            value_ar = value_ar[mask]
            length = len(index_ar)
            zero_ar = np.zeros(length)
            nan_ar = np.empty(length)
            nan_ar[:] = np.nan
            data_x = np.repeat(index_ar, 3)
            data_y = np.stack([nan_ar, zero_ar, value_ar], axis=1).reshape(-1)
            widget = self.root.simulation_lines["last_volume"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # book tickers
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            data_x = realtime_data["index"].astype(np.int64) / 10**9
            data_y = realtime_data[str((symbol, "Best Bid Price"))]
            mask = data_y != 0
            data_y = data_y[mask]
            data_x = data_x[mask]
            widget = self.root.simulation_lines["book_tickers"][0]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

            data_x = realtime_data["index"].astype(np.int64) / 10**9
            data_y = realtime_data[str((symbol, "Best Ask Price"))]
            mask = data_y != 0
            data_y = data_y[mask]
            data_x = data_x[mask]
            widget = self.root.simulation_lines["book_tickers"][1]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # price indicators
        is_light_line = True if is_fast_strategy else False
        if (only_light_lines and is_light_line) or not only_light_lines:
            df = indicators[symbol]["Price"]
            data_x = df.index.to_numpy(dtype=np.int64) / 10**9
            if not is_fast_strategy:
                data_x += 5
            line_list = self.root.simulation_lines["price_indicators"]
            for turn, widget in enumerate(line_list):
                if turn < len(df.columns):
                    column_name = df.columns[turn]
                    sr = df[column_name]
                    data_y = sr.to_numpy(dtype=np.float32)
                    inside_strings = re.findall(r"\(([^)]+)", column_name)
                    if len(inside_strings) == 0:
                        color = "#AAAAAA"
                    else:
                        color = inside_strings[0]

                    def job(widget=widget, data_x=data_x, data_y=data_y, color=color):
                        widget.setPen(color)
                        widget.setData(data_x, data_y)

                    if not only_light_lines:
                        if stop_flag.find("display_simulation_lines", task_id):
                            return
                    self.root.undertake(job, False)
                elif not only_light_lines:
                    if not only_light_lines:
                        if stop_flag.find("display_simulation_lines", task_id):
                            return
                    self.root.undertake(lambda w=widget: w.clear(), False)

        # price movement
        is_light_line = False
        if (only_light_lines and is_light_line) or not only_light_lines:
            index_ar = candle_data.index.to_numpy(dtype=np.int64) / 10**9
            index_ar += 5
            open_ar = candle_data[(symbol, "Open")].to_numpy()
            close_ar = candle_data[(symbol, "Close")].to_numpy()
            length = len(index_ar)
            nan_ar = np.empty(length)
            nan_ar[:] = np.nan
            data_x = np.repeat(index_ar, 3)
            data_y = np.stack([nan_ar, open_ar, close_ar], axis=1).reshape(-1)
            widget = self.root.simulation_lines["price_movement"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # close price
        is_light_line = False
        if (only_light_lines and is_light_line) or not only_light_lines:
            close_ar = candle_data[(symbol, "Close")].to_numpy()
            index_ar = candle_data.index.to_numpy(dtype=np.int64) / 10**9
            left_ar = index_ar + 2
            right_ar = index_ar + 8
            length = len(index_ar)
            nan_ar = np.empty(length)
            nan_ar[:] = np.nan
            data_x = np.stack([index_ar, left_ar, right_ar], axis=1).reshape(-1)
            data_y = np.stack([nan_ar, close_ar, close_ar], axis=1).reshape(-1)
            widget = self.root.simulation_lines["close_price"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # wobbles
        is_light_line = False
        if (only_light_lines and is_light_line) or not only_light_lines:
            sr = candle_data[(symbol, "High")]
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.simulation_lines["wobbles"][0]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

            sr = candle_data[(symbol, "Low")]
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.simulation_lines["wobbles"][1]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # open orders
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            boundaries = [
                open_order["boundary"]
                for open_order in self.account_state["open_orders"][symbol].values()
                if "boundary" in open_order
            ]
            first_moment = self.account_state["observed_until"] - timedelta(hours=12)
            last_moment = self.account_state["observed_until"] + timedelta(hours=12)
            for turn, widget in enumerate(self.root.simulation_lines["boundaries"]):
                if turn < len(boundaries):
                    boundary = boundaries[turn]
                    data_x = np.linspace(
                        first_moment.timestamp(), last_moment.timestamp(), num=1000
                    )
                    data_y = np.linspace(boundary, boundary, num=1000)
                    widget = self.root.simulation_lines["boundaries"][turn]

                    def job(widget=widget, data_x=data_x, data_y=data_y):
                        widget.setData(data_x, data_y)

                    if not only_light_lines:
                        if stop_flag.find("display_simulation_lines", task_id):
                            return
                    self.root.undertake(job, False)
                elif not only_light_lines:
                    if not only_light_lines:
                        if stop_flag.find("display_simulation_lines", task_id):
                            return
                    self.root.undertake(lambda w=widget: w.clear(), False)

        # trade volume indicators
        is_light_line = True if is_fast_strategy else False
        if (only_light_lines and is_light_line) or not only_light_lines:
            df = indicators[symbol]["Volume"]
            data_x = df.index.to_numpy(dtype=np.int64) / 10**9
            if not is_fast_strategy:
                data_x += 5
            line_list = self.root.simulation_lines["volume_indicators"]
            for turn, widget in enumerate(line_list):
                if turn < len(df.columns):
                    column_name = df.columns[turn]
                    sr = df[column_name]
                    data_y = sr.to_numpy(dtype=np.float32)
                    inside_strings = re.findall(r"\(([^)]+)", column_name)
                    if len(inside_strings) == 0:
                        color = "#AAAAAA"
                    else:
                        color = inside_strings[0]

                    def job(widget=widget, data_x=data_x, data_y=data_y, color=color):
                        widget.setPen(color)
                        widget.setData(data_x, data_y)

                    if not only_light_lines:
                        if stop_flag.find("display_simulation_lines", task_id):
                            return
                    self.root.undertake(job, False)
                elif not only_light_lines:
                    if not only_light_lines:
                        if stop_flag.find("display_simulation_lines", task_id):
                            return
                    self.root.undertake(lambda w=widget: w.clear(), False)

        # trade volume
        is_light_line = False
        if (only_light_lines and is_light_line) or not only_light_lines:
            sr = candle_data[(symbol, "Volume")]
            sr = sr.fillna(value=0)
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.simulation_lines["volume"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # abstract indicators indicators
        is_light_line = True if is_fast_strategy else False
        if (only_light_lines and is_light_line) or not only_light_lines:
            df = indicators[symbol]["Abstract"]
            data_x = df.index.to_numpy(dtype=np.int64) / 10**9
            if not is_fast_strategy:
                data_x += 5
            line_list = self.root.simulation_lines["abstract_indicators"]
            for turn, widget in enumerate(line_list):
                if turn < len(df.columns):
                    column_name = df.columns[turn]
                    sr = df[column_name]
                    data_y = sr.to_numpy(dtype=np.float32)
                    inside_strings = re.findall(r"\(([^)]+)", column_name)
                    if len(inside_strings) == 0:
                        color = "#AAAAAA"
                    else:
                        color = inside_strings[0]

                    def job(widget=widget, data_x=data_x, data_y=data_y, color=color):
                        widget.setPen(color)
                        widget.setData(data_x, data_y)

                    if not only_light_lines:
                        if stop_flag.find("display_simulation_lines", task_id):
                            return
                    self.root.undertake(job, False)
                elif not only_light_lines:
                    if not only_light_lines:
                        if stop_flag.find("display_simulation_lines", task_id):
                            return
                    self.root.undertake(lambda w=widget: w.clear(), False)

        # asset
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            data_x = (
                asset_record["Result Asset"].index.to_numpy(dtype=np.int64) / 10**9
            )
            data_y = asset_record["Result Asset"].to_numpy(dtype=np.float32)
            widget = self.root.simulation_lines["asset"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # asset with unrealized profit
        is_light_line = False
        if (only_light_lines and is_light_line) or not only_light_lines:
            if len(asset_record) >= 2:
                sr = asset_record["Result Asset"].resample("10S").ffill()
            unrealized_changes_sr = unrealized_changes.reindex(sr.index)
            sr = sr * (1 + unrealized_changes_sr)
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9 + 5
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.simulation_lines["asset_with_unrealized_profit"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # buy and sell
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            df = asset_record.loc[asset_record["Symbol"] == symbol]
            df = df[df["Side"] == "sell"]
            sr = df["Fill Price"]
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.simulation_lines["sell"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

            df = asset_record.loc[asset_record["Symbol"] == symbol]
            df = df[df["Side"] == "buy"]
            sr = df["Fill Price"]
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.simulation_lines["buy"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

        # entry price
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            entry_price = self.account_state["positions"][symbol]["entry_price"]
            first_moment = self.account_state["observed_until"] - timedelta(hours=12)
            last_moment = self.account_state["observed_until"] + timedelta(hours=12)
            if entry_price != 0:
                data_x = np.linspace(
                    first_moment.timestamp(), last_moment.timestamp(), num=1000
                )
                data_y = np.linspace(entry_price, entry_price, num=1000)
            else:
                data_x = []
                data_y = []
            widget = self.root.simulation_lines["entry_price"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_simulation_lines", task_id):
                    return
            self.root.undertake(job, False)

    def erase(self, *args, **kwargs):

        self.raw_account_state = {
            "observed_until": datetime.now(timezone.utc),
            "wallet_balance": 1,
            "positions": {},
            "open_orders": {},
        }
        for symbol in standardize.get_basics()["target_symbols"]:
            self.raw_account_state["positions"][symbol] = {
                "margin": 0,
                "direction": "none",
                "entry_price": 0,
                "update_time": datetime.fromtimestamp(0, tz=timezone.utc),
            }
            self.raw_account_state["open_orders"][symbol] = {}
        self.raw_scribbles = {}
        self.raw_asset_record = pd.DataFrame(
            columns=[
                "Cause",
                "Symbol",
                "Side",
                "Fill Price",
                "Role",
                "Margin Ratio",
                "Order ID",
                "Result Asset",
            ],
            index=pd.DatetimeIndex([], tz="UTC"),
        )
        self.raw_unrealized_changes = pd.Series(
            index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32
        )
        self.about_viewing = None

        self.present()

    def display_available_years(self, *args, **kwargs):

        with self.root.collector.datalocks[0]:
            years_sr = self.root.collector.candle_data.index.year.drop_duplicates()
        years = years_sr.tolist()
        years.sort(reverse=True)
        years = [str(year) for year in years]

        def job():
            widget = self.root.comboBox_5
            return [int(widget.itemText(i)) for i in range(widget.count())]

        choices = self.root.undertake(job, True)
        choices.sort(reverse=True)
        choices = [str(choice) for choice in choices]

        if years != choices:
            # if it's changed
            widget = self.root.comboBox_5
            self.root.undertake(lambda w=widget: w.clear(), False)
            self.root.undertake(lambda w=widget, y=years: w.addItems(y), False)

    def simulate_only_visible(self, *args, **kwargs):
        self.calculate(only_visible=True)

    def display_range_information(self, *args, **kwargs):

        task_id = stop_flag.make("display_simulation_range_information")

        symbol = self.viewing_symbol

        range_start = self.root.undertake(
            lambda: self.root.plot_widget_2.getAxis("bottom").range[0], True
        )
        range_start = max(range_start, 0)
        range_start = datetime.fromtimestamp(range_start, tz=timezone.utc)

        if stop_flag.find("display_simulation_range_information", task_id):
            return

        range_end = self.root.undertake(
            lambda: self.root.plot_widget_2.getAxis("bottom").range[1], True
        )
        if range_end < 0:
            # case when pyqtgraph passed negative value because it's too big
            range_end = 9223339636
        else:
            # maximum value available in pandas
            range_end = min(range_end, 9223339636)
        range_end = datetime.fromtimestamp(range_end, tz=timezone.utc)

        if stop_flag.find("display_simulation_range_information", task_id):
            return

        range_length = range_end - range_start
        range_days = range_length.days
        range_hours, remains = divmod(range_length.seconds, 3600)
        range_minutes, remains = divmod(remains, 60)
        range_length_text = f"{range_days}일 {range_hours}시간 {range_minutes}분"

        if stop_flag.find("display_simulation_range_information", task_id):
            return

        with self.datalocks[0]:
            unrealized_changes = self.unrealized_changes[range_start:range_end].copy()
        with self.datalocks[1]:
            asset_record = self.asset_record[range_start:range_end].copy()

        asset_changes = asset_record["Result Asset"].pct_change() + 1
        asset_changes = asset_changes.reindex(asset_record.index).fillna(value=1)
        symbol_mask = asset_record["Symbol"] == symbol

        # trade count
        total_change_count = len(asset_changes)
        symbol_change_count = len(asset_changes[symbol_mask])
        # trade volume
        if len(asset_record) > 0:
            total_margin_ratio = asset_record["Margin Ratio"].sum()
        else:
            total_margin_ratio = 0
        if len(asset_record[symbol_mask]) > 0:
            symbol_margin_ratio = asset_record[symbol_mask]["Margin Ratio"].sum()
        else:
            symbol_margin_ratio = 0
        # asset changes
        if len(asset_changes) > 0:
            total_yield = asset_changes.cumprod().iloc[-1]
            total_yield = (total_yield - 1) * 100
        else:
            total_yield = 0
        if len(asset_changes[symbol_mask]) > 0:
            symbol_yield = asset_changes[symbol_mask].cumprod().iloc[-1]
            symbol_yield = (symbol_yield - 1) * 100
        else:
            symbol_yield = 0
        # least unrealized changes
        if len(unrealized_changes) > 0:
            min_unrealized_change = unrealized_changes.min()
        else:
            min_unrealized_change = 0

        if stop_flag.find("display_simulation_range_information", task_id):
            return

        range_down = self.root.undertake(
            lambda: self.root.plot_widget_2.getAxis("left").range[0], True
        )
        range_up = self.root.undertake(
            lambda: self.root.plot_widget_2.getAxis("left").range[1], True
        )
        range_height = round((1 - range_down / range_up) * 100, 2)

        text = ""
        text += f"보이는 범위 {range_length_text}"
        text += "  ⦁  "
        text += f"보이는 가격대 {range_height}%"
        text += "  ⦁  "
        text += f"거래 횟수 {symbol_change_count}/{total_change_count}"
        text += "  ⦁  "
        text += f"거래량 {round(symbol_margin_ratio,4)}/{round(total_margin_ratio,4)}회분"
        text += "  ⦁  "
        text += f"누적 실현 수익률 {round(symbol_yield,4)}/{round(total_yield,4)}%"
        text += "  ⦁  "
        text += f"최저 미실현 수익률 {round(min_unrealized_change*100,2)}%"
        self.root.undertake(lambda t=text: self.root.label_13.setText(t), False)

    def set_minimum_view_range(self, *args, **kwargs):
        def job():
            range_up = self.root.plot_widget_2.getAxis("left").range[1]
            self.root.plot_widget_2.plotItem.vb.setLimits(minYRange=range_up * 0.004)
            range_up = self.root.plot_widget_3.getAxis("left").range[1]
            self.root.plot_widget_3.plotItem.vb.setLimits(minYRange=range_up * 0.004)

        self.root.undertake(job, False)

    def calculate(self, *args, **kwargs):

        task_id = stop_flag.make("calculate_simulation")

        only_visible = kwargs.get("only_visible", False)

        prepare_step = 0
        calculate_step = 0

        def job():
            while True:
                if stop_flag.find("calculate_simulation", task_id):
                    widget = self.root.progressBar_4
                    self.root.undertake(lambda w=widget: w.setValue(0), False)
                    widget = self.root.progressBar
                    self.root.undertake(lambda w=widget: w.setValue(0), False)
                    return
                else:
                    if prepare_step == 6 and calculate_step == 1000:
                        is_progressbar_filled = True
                        progressbar_value = self.root.undertake(
                            lambda: self.root.progressBar_4.value(), True
                        )
                        if progressbar_value < 1000:
                            is_progressbar_filled = False
                        progressbar_value = self.root.undertake(
                            lambda: self.root.progressBar.value(), True
                        )
                        if progressbar_value < 1000:
                            is_progressbar_filled = False
                        if is_progressbar_filled:
                            time.sleep(0.1)
                            widget = self.root.progressBar_4
                            self.root.undertake(lambda w=widget: w.setValue(0), False)
                            widget = self.root.progressBar
                            self.root.undertake(lambda w=widget: w.setValue(0), False)
                            return
                    widget = self.root.progressBar_4
                    before_value = self.root.undertake(lambda w=widget: w.value(), True)
                    if before_value < 1000:
                        remaining = math.ceil(1000 / 6 * prepare_step) - before_value
                        new_value = before_value + math.ceil(remaining * 0.2)
                        self.root.undertake(
                            lambda w=widget, v=new_value: w.setValue(v), False
                        )
                    widget = self.root.progressBar
                    before_value = self.root.undertake(lambda w=widget: w.value(), True)
                    if before_value < 1000:
                        remaining = calculate_step - before_value
                        new_value = before_value + math.ceil(remaining * 0.2)
                        self.root.undertake(
                            lambda w=widget, v=new_value: w.setValue(v), False
                        )
                    time.sleep(0.01)

        thread_toss.apply_async(job)

        prepare_step = 1

        # ■■■■■ default values and the strategy ■■■■■

        year = self.calculation_settings["year"]
        strategy = self.calculation_settings["strategy"]

        asset_record_filepath = (
            f"{self.workerpath}/{strategy}_{year}_asset_record.pickle"
        )
        unrealized_changes_filepath = (
            f"{self.workerpath}/{strategy}_{year}_unrealized_changes.pickle"
        )
        scribbles_filepath = f"{self.workerpath}/{strategy}_{year}_scribbles.pickle"
        account_state_filepath = (
            f"{self.workerpath}/{strategy}_{year}_account_state.pickle"
        )
        virtual_state_filepath = (
            f"{self.workerpath}/{strategy}_{year}_virtual_state.pickle"
        )

        if strategy == 0:
            strategy_details = self.root.strategist.details
        else:
            for strategy_tuple in self.root.strategy_tuples:
                if strategy_tuple[0] == strategy:
                    strategy_details = strategy_tuple[2]
        is_working_strategy = strategy_details[0]
        should_parallalize = strategy_details[1]
        unit_length = strategy_details[2]
        is_fast_strategy = strategy_details[3]

        if not is_working_strategy:
            stop_flag.make("calculate_simulation")
            question = [
                "사용 가능 전략이 아닙니다.",
                "다른 전략을 선택하세요.",
                ["확인"],
                False,
            ]
            self.root.ask(question)
            return

        prepare_step = 2

        # ■■■■■ observed data of the year ■■■■■

        if is_fast_strategy:
            # get all
            with self.root.collector.datalocks[1]:
                original_chunks = self.root.collector.realtime_data_chunks
                realtime_data_chunks = copy.deepcopy(original_chunks)
            ar = np.concatenate(realtime_data_chunks)
            year_observed_data = process_toss.apply(digitize.do, ar)
        else:
            # get only year range
            with self.root.collector.datalocks[0]:
                df = self.root.collector.candle_data
                year_observed_data = df[df.index.year == year].copy()
            # slice until last hour
            slice_until = year_observed_data.index[-1] + timedelta(seconds=10)
            slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
            slice_until -= timedelta(seconds=1)
            year_observed_data = year_observed_data[:slice_until]
            # interpolate
            year_observed_data = year_observed_data.interpolate()

        prepare_step = 3

        # ■■■■■ prepare data and calculation range ■■■■■

        blank_asset_record = pd.DataFrame(
            columns=[
                "Cause",
                "Symbol",
                "Side",
                "Fill Price",
                "Role",
                "Margin Ratio",
                "Order ID",
                "Result Asset",
            ],
            index=pd.DatetimeIndex([], tz="UTC"),
        )
        blank_unrealized_changes = pd.Series(
            index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32
        )
        blank_scribbles = {}
        blank_account_state = {
            "observed_until": datetime.now(timezone.utc),
            "wallet_balance": 1,
            "positions": {},
            "open_orders": {},
        }
        for symbol in standardize.get_basics()["target_symbols"]:
            blank_account_state["positions"][symbol] = {
                "margin": 0,
                "direction": "none",
                "entry_price": 0,
                "update_time": datetime.fromtimestamp(0, tz=timezone.utc),
            }
            blank_account_state["open_orders"][symbol] = {}
        blank_virtual_state = {
            "available_balance": 1,
            "locations": {},
            "placements": {},
        }
        for symbol in standardize.get_basics()["target_symbols"]:
            blank_virtual_state["locations"][symbol] = {
                "amount": 0,
                "entry_price": 0,
            }
            blank_virtual_state["placements"][symbol] = {}

        prepare_step = 4

        if only_visible:
            # when calculating only visible range

            previous_asset_record = blank_asset_record.copy()
            previous_unrealized_changes = blank_unrealized_changes.copy()
            previous_scribbles = blank_scribbles.copy()
            previous_account_state = blank_account_state.copy()
            previous_virtual_state = blank_virtual_state.copy()

            range_start = self.root.undertake(
                lambda: self.root.plot_widget_2.getAxis("bottom").range[0], True
            )
            range_start = datetime.fromtimestamp(range_start, tz=timezone.utc)
            range_start = range_start.replace(microsecond=0)
            range_start = range_start - timedelta(seconds=range_start.second % 10)

            range_end = self.root.undertake(
                lambda: self.root.plot_widget_2.getAxis("bottom").range[1], True
            )
            range_end = datetime.fromtimestamp(range_end, tz=timezone.utc)
            range_end = range_end.replace(microsecond=0)
            range_end = range_end - timedelta(seconds=range_end.second % 10)
            range_end += timedelta(seconds=10)

            calculate_from = max(range_start, year_observed_data.index[0])
            calculate_until = min(range_end, year_observed_data.index[-1])

        else:
            # when calculating properly
            try:
                previous_asset_record = pd.read_pickle(asset_record_filepath)
                previous_unrealized_changes = pd.read_pickle(
                    unrealized_changes_filepath
                )
                with open(scribbles_filepath, "rb") as file:
                    previous_scribbles = pickle.load(file)
                with open(account_state_filepath, "rb") as file:
                    previous_account_state = pickle.load(file)
                with open(virtual_state_filepath, "rb") as file:
                    previous_virtual_state = pickle.load(file)

                calculate_from = previous_account_state["observed_until"]
                calculate_until = year_observed_data.index[-1]
            except FileNotFoundError:
                previous_asset_record = blank_asset_record.copy()
                previous_unrealized_changes = blank_unrealized_changes.copy()
                previous_scribbles = blank_scribbles.copy()
                previous_account_state = blank_account_state.copy()
                previous_virtual_state = blank_virtual_state.copy()

                calculate_from = year_observed_data.index[0]
                calculate_until = year_observed_data.index[-1]

        should_calculate = calculate_from < calculate_until
        if len(previous_asset_record) == 0:
            previous_asset_record.loc[calculate_from, "Cause"] = "other"
            previous_asset_record.loc[calculate_from, "Result Asset"] = float(1)

        prepare_step = 5

        # ■■■■■ prepare per unit data ■■■■■

        if should_calculate:

            decision_script = self.root.strategist.decision_script
            indicators_script = self.root.strategist.indicators_script
            compiled_indicators_script = compile(indicators_script, "<string>", "exec")

            slice_from = calculate_from - timedelta(days=7)
            # a little more data for generation
            slice_to = calculate_until
            year_indicators = process_toss.apply(
                make_indicators.do,
                observed_data=year_observed_data[slice_from:slice_to],
                strategy=strategy,
                compiled_custom_script=compiled_indicators_script,
            )

            if should_parallalize:

                needed_candle_data = year_observed_data[calculate_from:calculate_until]
                if is_fast_strategy:
                    frequency = timedelta(minutes=unit_length)
                else:
                    frequency = timedelta(days=unit_length)
                unit_observed_data_list = [
                    unit_observed_data
                    for _, unit_observed_data in needed_candle_data.groupby(
                        pd.Grouper(freq=frequency, origin="epoch")
                    )
                ]

                communication_manager = multiprocessing.Manager()
                unit_count = len(unit_observed_data_list)
                progress_list = communication_manager.list([0] * unit_count)

                input_data = []
                for turn, unit_observed_data in enumerate(unit_observed_data_list):
                    base_index = unit_observed_data.index
                    unit_indicators = year_indicators.reindex(base_index)
                    get_from = base_index[0]
                    get_to = base_index[-1] + timedelta(seconds=10)
                    unit_asset_record = previous_asset_record[get_from:get_to]
                    unit_unrealized_changes = previous_unrealized_changes[
                        get_from:get_to
                    ]
                    if get_from < calculate_from <= get_to:
                        unit_scribbles = previous_scribbles
                        unit_account_state = previous_account_state
                        unit_virtual_state = previous_virtual_state
                    else:
                        unit_scribbles = blank_scribbles
                        unit_account_state = blank_account_state
                        unit_virtual_state = blank_virtual_state

                    dataset = {
                        "progress_list": progress_list,
                        "target_progress": turn,
                        "strategy": strategy,
                        "is_fast_strategy": is_fast_strategy,
                        "unit_observed_data": unit_observed_data,
                        "unit_indicators": unit_indicators,
                        "unit_asset_record": unit_asset_record,
                        "unit_unrealized_changes": unit_unrealized_changes,
                        "unit_scribbles": unit_scribbles,
                        "unit_account_state": unit_account_state,
                        "unit_virtual_state": unit_virtual_state,
                        "calculate_from": calculate_from,
                        "calculate_until": calculate_until,
                        "decision_script": decision_script,
                    }
                    input_data.append(dataset)

            else:

                communication_manager = multiprocessing.Manager()
                progress_list = communication_manager.list([0])

                input_data = []
                dataset = {
                    "progress_list": progress_list,
                    "target_progress": 0,
                    "strategy": strategy,
                    "is_fast_strategy": is_fast_strategy,
                    "unit_observed_data": year_observed_data,
                    "unit_indicators": year_indicators,
                    "unit_asset_record": previous_asset_record,
                    "unit_unrealized_changes": previous_unrealized_changes,
                    "unit_scribbles": previous_scribbles,
                    "unit_account_state": previous_account_state,
                    "unit_virtual_state": previous_virtual_state,
                    "calculate_from": calculate_from,
                    "calculate_until": calculate_until,
                    "decision_script": decision_script,
                }
                input_data.append(dataset)

        prepare_step = 6

        # ■■■■■ calculate ■■■■■

        if should_calculate:

            map_result = process_toss.map_async(simulate_unit.do, input_data)

            total_seconds = (calculate_until - calculate_from).total_seconds()
            while True:
                if map_result.ready():
                    if map_result.successful():
                        output_data = map_result.get()
                        break
                    else:
                        stop_flag.make("calculate_simulation")
                if stop_flag.find("calculate_simulation", task_id):
                    return
                total_progress = sum(progress_list)
                calculate_step = math.ceil(total_progress * 1000 / total_seconds)

        calculate_step = 1000

        # ■■■■■ get calculation result ■■■■■

        if should_calculate:

            asset_record = previous_asset_record
            for month_ouput_data in output_data:
                month_asset_record = month_ouput_data["unit_asset_record"]
                concat_data = [asset_record, month_asset_record]
                asset_record = pd.concat(concat_data)
            mask = ~asset_record.index.duplicated()
            asset_record = asset_record[mask]
            asset_record = asset_record.sort_index()

            unrealized_changes = previous_unrealized_changes
            for month_ouput_data in output_data:
                month_unrealized_changes = month_ouput_data["unit_unrealized_changes"]
                concat_data = [unrealized_changes, month_unrealized_changes]
                unrealized_changes = pd.concat(concat_data)
            mask = ~unrealized_changes.index.duplicated()
            unrealized_changes = unrealized_changes[mask]
            unrealized_changes = unrealized_changes.sort_index()

            scribbles = output_data[-1]["unit_scribbles"]
            account_state = output_data[-1]["unit_account_state"]
            virtual_state = output_data[-1]["unit_virtual_state"]

        else:

            asset_record = previous_asset_record
            unrealized_changes = previous_unrealized_changes
            scribbles = previous_scribbles
            account_state = previous_account_state

        # ■■■■■ remember and present ■■■■■

        self.raw_asset_record = asset_record
        self.raw_unrealized_changes = unrealized_changes
        self.raw_scribbles = scribbles
        self.raw_account_state = account_state
        self.about_viewing = {"year": year, "strategy": strategy}
        self.present()

        # ■■■■■ save if properly calculated ■■■■■

        if not only_visible and should_calculate:

            asset_record.to_pickle(asset_record_filepath)
            unrealized_changes.to_pickle(unrealized_changes_filepath)
            with open(scribbles_filepath, "wb") as file:
                pickle.dump(scribbles, file)
            with open(account_state_filepath, "wb") as file:
                pickle.dump(account_state, file)
            with open(virtual_state_filepath, "wb") as file:
                pickle.dump(virtual_state, file)

    def present(self, *args, **kwargs):

        maker_fee = self.presentation_settings["maker_fee"]
        taker_fee = self.presentation_settings["taker_fee"]
        leverage = self.presentation_settings["leverage"]

        with self.datalocks[0]:
            asset_record = self.raw_asset_record.copy()
            unrealized_changes = self.raw_unrealized_changes.copy()
            scribbles = self.raw_scribbles.copy()
            account_state = self.raw_account_state.copy()

        # ■■■■■ get strategy details ■■■■

        if self.about_viewing is None:
            should_parallalize = False
            unit_length = 0
        else:
            strategy = self.about_viewing["strategy"]
            if strategy == 0:
                strategy_details = self.root.strategist.details
            else:
                for strategy_tuple in self.root.strategy_tuples:
                    if strategy_tuple[0] == strategy:
                        strategy_details = strategy_tuple[2]
            should_parallalize = strategy_details[1]
            unit_length = strategy_details[2]
            is_fast_strategy = strategy_details[3]

        # ■■■■■ apply other factors to the asset trace ■■■■

        if should_parallalize:
            if is_fast_strategy:
                frequency = timedelta(minutes=unit_length)
            else:
                frequency = timedelta(days=unit_length)
            unit_asset_record_list = [
                unit_asset_record.dropna()
                for _, unit_asset_record in asset_record.groupby(
                    pd.Grouper(freq=frequency, origin="epoch")
                )
            ]
            unit_count = len(unit_asset_record_list)

        else:
            unit_asset_record_list = [asset_record]
            unit_count = 1

        unit_asset_changes_list = []
        for turn in range(unit_count):

            unit_asset_record = unit_asset_record_list[turn]

            # leverage
            unit_asset_shifts = unit_asset_record["Result Asset"].diff()
            if len(unit_asset_shifts) > 0:
                unit_asset_shifts.iloc[0] = 0
            lazy_unit_result_asset = unit_asset_record["Result Asset"].shift(periods=1)
            if len(lazy_unit_result_asset) > 0:
                lazy_unit_result_asset.iloc[0] = 1
            unit_asset_changes_by_leverage = (
                1 + unit_asset_shifts / lazy_unit_result_asset * leverage
            )

            # fee
            month_fees = unit_asset_record["Role"].copy()
            month_fees[month_fees == "maker"] = maker_fee
            month_fees[month_fees == "taker"] = taker_fee
            month_fees = month_fees.astype(np.float32)
            month_margin_ratios = unit_asset_record["Margin Ratio"]
            month_asset_changes_by_fee = (
                1 - (month_fees / 100) * month_margin_ratios * leverage
            )

            # altogether
            month_asset_changes = (
                unit_asset_changes_by_leverage * month_asset_changes_by_fee
            )
            unit_asset_changes_list.append(month_asset_changes)

        year_asset_changes = pd.concat(unit_asset_changes_list).sort_index()

        if len(year_asset_changes) > 0:
            year_asset_changes.iloc[0] = float(1)

        unrealized_changes = unrealized_changes * leverage

        presentation_asset_record = asset_record.copy()
        presentation_unrealized_changes = unrealized_changes.copy()
        presentation_scribbles = scribbles.copy()
        presentation_account_state = account_state.copy()

        # ■■■■■ remember ■■■■■

        self.scribbles = presentation_scribbles
        self.account_state = presentation_account_state
        with self.datalocks[0]:
            self.unrealized_changes = presentation_unrealized_changes
        with self.datalocks[1]:
            self.asset_record = presentation_asset_record

        # ■■■■■ display ■■■■■

        self.display_lines()
        self.display_range_information()

        if self.about_viewing is None:
            text = "아무 전략도 그려져 있지 않음"
            self.root.undertake(lambda t=text: self.root.label_19.setText(t), False)
        else:
            year = self.about_viewing["year"]
            strategy = self.about_viewing["strategy"]
            text = ""
            text += f"범위 {year}년"
            text += "  ⦁  "
            text += f"전략 {strategy}번"
            self.root.undertake(lambda t=text: self.root.label_19.setText(t), False)

    def toggle_vertical_automation(self, *args, **kwargs):
        state = args[0]
        if state == QtCore.Qt.CheckState.Checked.value:
            self.root.plot_widget_2.setMouseEnabled(y=True)
            self.root.plot_widget_3.setMouseEnabled(y=True)
            self.root.plot_widget_5.setMouseEnabled(y=True)
            self.root.plot_widget_7.setMouseEnabled(y=True)
            self.root.plot_widget_2.enableAutoRange(y=False)
            self.root.plot_widget_3.enableAutoRange(y=False)
            self.root.plot_widget_5.enableAutoRange(y=False)
            self.root.plot_widget_7.enableAutoRange(y=False)
        else:
            self.root.plot_widget_2.setMouseEnabled(y=False)
            self.root.plot_widget_3.setMouseEnabled(y=False)
            self.root.plot_widget_5.setMouseEnabled(y=False)
            self.root.plot_widget_7.setMouseEnabled(y=False)
            self.root.plot_widget_2.enableAutoRange(y=True)
            self.root.plot_widget_3.enableAutoRange(y=True)
            self.root.plot_widget_5.enableAutoRange(y=True)
            self.root.plot_widget_7.enableAutoRange(y=True)

    def display_year_range(self, *args, **kwargs):
        range_start = datetime(
            year=self.calculation_settings["year"],
            month=1,
            day=1,
            tzinfo=timezone.utc,
        )
        range_start = range_start.timestamp()
        range_end = datetime(
            year=self.calculation_settings["year"] + 1,
            month=1,
            day=1,
            tzinfo=timezone.utc,
        )
        range_end = range_end.timestamp()
        widget = self.root.plot_widget_2

        def job(range_start=range_start, range_end=range_end):
            widget.setXRange(range_start, range_end)

        self.root.undertake(job, False)

    def delete_calculation_data(self, *args, **kwargs):
        year = self.calculation_settings["year"]
        strategy = self.calculation_settings["strategy"]

        asset_record_filepath = (
            f"{self.workerpath}/{strategy}_{year}_asset_record.pickle"
        )
        unrealized_changes_filepath = (
            f"{self.workerpath}/{strategy}_{year}_unrealized_changes.pickle"
        )
        scribbles_filepath = f"{self.workerpath}/{strategy}_{year}_scribbles.pickle"
        account_state_filepath = (
            f"{self.workerpath}/{strategy}_{year}_account_state.pickle"
        )
        virtual_state_filepath = (
            f"{self.workerpath}/{strategy}_{year}_virtual_state.pickle"
        )

        does_file_exist = False

        if os.path.exists(asset_record_filepath):
            does_file_exist = True
        if os.path.exists(unrealized_changes_filepath):
            does_file_exist = True
        if os.path.exists(scribbles_filepath):
            does_file_exist = True
        if os.path.exists(account_state_filepath):
            does_file_exist = True
        if os.path.exists(virtual_state_filepath):
            does_file_exist = True

        if not does_file_exist:
            question = [
                f"{year}년의 {strategy}번 전략 계산 데이터는 없습니다.",
                "계산하기 버튼을 누른다면 해당 연도의 처음부터 계산하게 됩니다.",
                ["확인"],
                False,
            ]
            self.root.ask(question)
            return
        else:
            question = [
                f"{year}년의 {strategy}번 전략 계산 데이터를 삭제하시겠어요?",
                "삭제하고 나서 이 조합의 시뮬레이션을 다시 보려면 해당 연도 전체를 다시 계산해야 합니다. 다른 조합의 계산 데이터는 영향을"
                " 받지 않습니다.",
                ["취소", "삭제"],
                False,
            ]
            answer = self.root.ask(question)
            if answer in (0, 1):
                return

        try:
            os.remove(asset_record_filepath)
        except FileNotFoundError:
            pass
        try:
            os.remove(unrealized_changes_filepath)
        except FileNotFoundError:
            pass
        try:
            os.remove(scribbles_filepath)
        except FileNotFoundError:
            pass
        try:
            os.remove(account_state_filepath)
        except FileNotFoundError:
            pass
        try:
            os.remove(virtual_state_filepath)
        except FileNotFoundError:
            pass

        self.erase()

    def draw(self, *args, **kwargs):

        year = self.calculation_settings["year"]
        strategy = self.calculation_settings["strategy"]

        asset_record_filepath = (
            f"{self.workerpath}/{strategy}_{year}_asset_record.pickle"
        )
        unrealized_changes_filepath = (
            f"{self.workerpath}/{strategy}_{year}_unrealized_changes.pickle"
        )
        scribbles_filepath = f"{self.workerpath}/{strategy}_{year}_scribbles.pickle"
        account_state_filepath = (
            f"{self.workerpath}/{strategy}_{year}_account_state.pickle"
        )

        try:
            with self.datalocks[0]:
                self.raw_asset_record = pd.read_pickle(asset_record_filepath)
                self.raw_unrealized_changes = pd.read_pickle(
                    unrealized_changes_filepath
                )
                with open(scribbles_filepath, "rb") as file:
                    self.raw_scribbles = pickle.load(file)
                with open(account_state_filepath, "rb") as file:
                    self.raw_account_state = pickle.load(file)
            self.about_viewing = {"year": year, "strategy": strategy}
            self.present()
        except FileNotFoundError:
            question = [
                f"{year}년의 {strategy}번 전략 계산 데이터는 없습니다.",
                "계산을 먼저 해야 그릴 수 있습니다.",
                ["확인"],
                False,
            ]
            self.root.ask(question)
            return

    def match_graph_range(self, *args, **kwargs):
        range_start = self.root.undertake(
            lambda: self.root.plot_widget.getAxis("bottom").range[0], True
        )
        range_end = self.root.undertake(
            lambda: self.root.plot_widget.getAxis("bottom").range[1], True
        )
        widget = self.root.plot_widget_2

        def job(range_start=range_start, range_end=range_end):
            widget.setXRange(range_start, range_end, padding=0)

        self.root.undertake(job, False)

    def stop_calculation(self, *args, **kwargs):
        stop_flag.make("calculate_simulation")

    def analyze_unrealized_peaks(self, *args, **kwargs):
        peak_indexes, _ = find_peaks(-self.unrealized_changes, distance=3600 / 10)
        peak_sr = self.unrealized_changes.iloc[peak_indexes]
        peak_sr = peak_sr.sort_values().iloc[:12]
        if len(peak_sr) < 12:
            question = [
                "계산 데이터가 너무 짧거나 없습니다.",
                "유의미한 최저 미실현 수익률 목록을 알아낼 수 없습니다.",
                ["확인"],
                False,
            ]
            self.root.ask(question)
        else:
            text_lines = [
                str(index) + " " + str(round(peak_value * 100, 2)) + "%"
                for index, peak_value in peak_sr.iteritems()
            ]
            question = [
                "최저 미실현 수익률을 기록한 지점들입니다.",
                "\n".join(text_lines),
                ["확인"],
                False,
            ]
            self.root.ask(question)
