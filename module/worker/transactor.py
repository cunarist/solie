from datetime import datetime, timedelta, timezone
import threading
import json
import os
import time
import webbrowser
import math
import re
from collections import deque
import pickle
import copy
import logging

import pandas as pd
import numpy as np
from PyQt6 import QtCore

from module.instrument.api_requester import ApiRequester
from module.instrument.api_streamer import ApiStreamer
from module.instrument.api_request_error import ApiRequestError
from module.recipe import decide
from module.recipe import make_indicators
from module.recipe import ball
from module.recipe import stop_flag
from module.recipe import check_internet
from module.recipe import digitize
from module.recipe import process_toss
from module.recipe import thread_toss
from module.recipe import standardize
from module.recipe import remember_task_durations


class Transactor:
    def __init__(self, root):

        # ■■■■■ the basic ■■■■■

        self.root = root

        # ■■■■■ for data management ■■■■■

        self.workerpath = standardize.get_datapath() + "/transactor"
        os.makedirs(self.workerpath, exist_ok=True)
        self.datalocks = [threading.Lock() for _ in range(8)]

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.viewing_symbol = standardize.get_basics()["target_symbols"][0]

        self.task_durations = {
            "decide_transacting_slow": deque(maxlen=360),
            "display_light_lines": deque(maxlen=60),
            "decide_transacting_fast": deque(maxlen=1280),
            "place_order": deque(maxlen=60),
        }

        self.account_state = {
            "observed_until": datetime.now(timezone.utc) - timedelta(days=7),
            "wallet_balance": 1,
            "positions": {},
            "open_orders": {},
        }
        for symbol in standardize.get_basics()["target_symbols"]:
            self.account_state["positions"][symbol] = {
                "margin": 0,
                "direction": "none",
                "entry_price": 0,
                "update_time": datetime.now(timezone.utc) - timedelta(days=7),
            }
            self.account_state["open_orders"][symbol] = {}

        self.hidden_state = {
            "leverages": {},
        }

        self.exchange_state = {
            "maximum_quantities": {},
            "minimum_notionals": {},
            "price_precisions": {},
            "quantity_precisions": {},
        }

        try:
            filepath = self.workerpath + "/scribbles.pickle"
            with open(filepath, "rb") as file:
                self.scribbles = pickle.load(file)
        except FileNotFoundError:
            self.scribbles = {}

        try:
            filepath = self.workerpath + "/automation_settings.json"
            with open(filepath, "r", encoding="utf8") as file:
                read_data = json.load(file)
            self.automation_settings = read_data
            state = read_data["should_transact"]
            self.root.undertake(lambda s=state: self.root.checkBox.setChecked(s), False)
            strategy = read_data["strategy"]
            for index, strategy_tuple in enumerate(self.root.strategy_tuples):
                if strategy == strategy_tuple[0]:
                    self.root.undertake(
                        lambda i=index: self.root.comboBox_2.setCurrentIndex(i), False
                    )

        except FileNotFoundError:
            self.automation_settings = {
                "strategy": 0,
                "should_transact": False,
            }

        try:
            filepath = self.workerpath + "/mode_settings.json"
            with open(filepath, "r", encoding="utf8") as file:
                read_data = json.load(file)
            self.mode_settings = read_data
            new_value = read_data["desired_leverage"]
            self.root.undertake(
                lambda n=new_value: self.root.spinBox.setValue(n), False
            )
        except FileNotFoundError:
            self.mode_settings = {
                "desired_leverage": 1,
            }

        try:
            filepath = self.workerpath + "/keys.json"
            with open(filepath, "r", encoding="utf8") as file:
                keys = json.load(file)
            text = keys["binance_api"]
            self.root.undertake(lambda t=text: self.root.lineEdit_4.setText(t), False)
            text = keys["binance_secret"]
            self.root.undertake(lambda t=text: self.root.lineEdit_6.setText(t), False)
            if keys["server"] == "real":
                index = 0
            elif keys["server"] == "testnet":
                index = 1
            self.root.undertake(
                lambda i=index: self.root.comboBox_3.setCurrentIndex(i), False
            )
            self.keys = keys
            self.api_requester.update_keys(keys)
        except FileNotFoundError:
            self.keys = {
                "server": "real",
                "binance_api": "",
                "binance_secret": "",
            }

        try:
            filepath = self.workerpath + "/trade_record.pickle"
            self.trade_record = pd.read_pickle(filepath)
            self.trade_record = self.trade_record.sort_index()
        except FileNotFoundError:
            self.trade_record = pd.DataFrame(
                columns=[
                    "Symbol",
                    "Side",
                    "Fill Price",
                    "Role",
                    "Margin Ratio",
                    "Order ID",
                ],
                index=pd.DatetimeIndex([], tz="UTC"),
            )

        try:
            self.asset_trace = pd.read_pickle(self.workerpath + "/asset_trace.pickle")
            self.asset_trace = self.asset_trace.sort_index()
            self.asset_trace = self.asset_trace.astype(np.float32)
        except FileNotFoundError:
            self.asset_trace = pd.Series(
                index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32
            )

        try:
            self.unrealized_changes = pd.read_pickle(
                self.workerpath + "/unrealized_changes.pickle"
            )
            self.unrealized_changes = self.unrealized_changes.sort_index()
            self.unrealized_changes = self.unrealized_changes.astype(np.float32)
        except FileNotFoundError:
            self.unrealized_changes = pd.Series(
                index=pd.DatetimeIndex([], tz="UTC"), dtype=np.float32
            )

        # ■■■■■ default executions ■■■■■

        self.root.initialize_functions.append(
            lambda: self.watch_binance(),
        )
        self.root.initialize_functions.append(
            lambda: self.update_user_data_stream(),
        )
        self.root.initialize_functions.append(
            lambda: self.display_lines(),
        )
        self.root.initialize_functions.append(
            lambda: self.display_day_range(),
        )
        self.root.finalize_functions.append(
            lambda: self.save_unrealized_changes(),
        )
        self.root.finalize_functions.append(
            lambda: self.save_scribbles(),
        )

        # ■■■■■ repetitive schedules ■■■■■

        self.root.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
            kwargs={"only_light_lines": True},
        )
        self.root.scheduler.add_job(
            self.display_asset_information,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.display_range_information,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.transact_fast,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.cancel_conflicting_orders,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.transact_slow,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.save_scribbles,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
            kwargs={"periodic": True},
        )
        self.root.scheduler.add_job(
            self.watch_binance,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.update_user_data_stream,
            trigger="cron",
            minute="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.save_unrealized_changes,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = [
            ApiStreamer(
                "",
                self.listen_to_account,
            ),
        ]

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functrions = [
            lambda: self.update_user_data_stream(),
            lambda: self.watch_binance(),
        ]
        check_internet.add_connected_functions(connected_functrions)

        disconnected_functions = []
        check_internet.add_disconnected_functions(disconnected_functions)

    def save_scribbles(self, *args, **kwargs):
        filepath = self.workerpath + "/scribbles.pickle"
        with open(filepath, "wb") as file:
            pickle.dump(self.scribbles, file)

    def update_user_data_stream(self, *args, **kwargs):

        if not check_internet.connected():
            return

        server = self.keys["server"]

        try:
            payload = {}
            response = self.api_requester.binance(
                http_method="POST",
                path="/fapi/v1/listenKey",
                payload=payload,
            )
        except ApiRequestError:
            return

        listen_key = response["listenKey"]

        api_streamer = self.api_streamers[0]
        if server == "real":
            url = "wss://fstream.binance.com/ws/" + listen_key
        elif server == "testnet":
            url = "wss://fstream.binancefuture.com/ws/" + listen_key
        api_streamer.update_url(url)

    def listen_to_account(self, *args, **kwargs):

        received = kwargs["received"]

        # ■■■■■ default values ■■■■■

        event_type = received["e"]
        event_timestamp = received["E"] / 1000
        event_time = datetime.fromtimestamp(event_timestamp, tz=timezone.utc)

        self.account_state["observed_until"] = event_time

        # ■■■■■ do the task according to event type ■■■■■

        if event_type == "listenKeyExpired":

            text = "Binance user data stream listen key got expired"
            logger = logging.getLogger("solsol")
            logger.warning(text)
            self.update_user_data_stream()

        if event_type == "ACCOUNT_UPDATE":

            about_update = received["a"]
            about_assets = about_update["B"]
            about_positions = about_update["P"]

            if "USDT" in [about_asset["a"] for about_asset in about_assets]:

                for about_asset in about_assets:
                    asset_name = about_asset["a"]
                    if asset_name == "USDT":
                        break

                wallet_balance = float(about_asset["wb"])
                self.wallet_balance_state = wallet_balance

            if "BOTH" in [about_position["ps"] for about_position in about_positions]:

                for about_position in about_positions:
                    position_side = about_position["ps"]
                    if position_side == "BOTH":
                        break

                target_symbols = standardize.get_basics()["target_symbols"]
                if about_position["s"] not in target_symbols:
                    return

                symbol = about_position["s"]
                amount = float(about_position["pa"])
                entry_price = float(about_position["ep"])

                leverage = self.hidden_state["leverages"][symbol]
                margin = abs(amount) * entry_price / leverage
                if amount == 0:
                    direction = "none"
                elif amount < 0:
                    direction = "short"
                elif amount > 0:
                    direction = "long"

                self.account_state["positions"][symbol]["margin"] = margin
                self.account_state["positions"][symbol]["direction"] = direction
                self.account_state["positions"][symbol]["entry_price"] = entry_price
                self.account_state["positions"][symbol]["update_time"] = event_time

        if event_type == "ORDER_TRADE_UPDATE":

            about_update = received["o"]

            target_symbols = standardize.get_basics()["target_symbols"]
            if about_update["s"] not in target_symbols:
                return

            # from received
            symbol = about_update.get("s")
            order_id = about_update.get("i")
            order_type = about_update.get("o")
            order_status = about_update.get("X")
            execution_type = about_update.get("x")

            side = about_update.get("S")
            close_position = about_update.get("cp")
            is_maker = about_update.get("m")

            origianal_quantity = float(about_update.get("q", 0))
            executed_quantity = float(about_update.get("z", 0))
            last_filled_quantity = float(about_update.get("l", 0))
            last_filled_price = float(about_update.get("L", 0))
            price = float(about_update.get("p", 0))
            stop_price = float(about_update.get("sp", 0))
            commission = float(about_update.get("n", 0))
            realized_profit = float(about_update.get("rp", 0))

            # from remembered
            leverage = self.hidden_state["leverages"][symbol]
            wallet_balance = self.account_state["wallet_balance"]

            # when the order is removed
            if order_status not in ("NEW", "PARTIALLY_FILLED"):

                if order_id in self.account_state["open_orders"][symbol].keys():
                    self.account_state["open_orders"][symbol].pop(order_id)

            # when the order is left or created
            if order_status in ("NEW", "PARTIALLY_FILLED"):

                if order_type == "STOP_MARKET":
                    if close_position:
                        if side == "BUY":
                            command_name = "later_up_close"
                            boundary = stop_price
                            left_margin = None
                        elif side == "SELL":
                            command_name = "later_down_close"
                            boundary = stop_price
                            left_margin = None
                    elif side == "BUY":
                        command_name = "later_up_buy"
                        boundary = stop_price
                        left_quantity = origianal_quantity
                        left_margin = left_quantity * boundary / leverage
                    elif side == "SELL":
                        command_name = "later_down_sell"
                        boundary = stop_price
                        left_quantity = origianal_quantity
                        left_margin = left_quantity * boundary / leverage
                elif order_type == "TAKE_PROFIT_MARKET":
                    if close_position:
                        if side == "BUY":
                            command_name = "later_down_close"
                            boundary = stop_price
                            left_margin = None
                        elif side == "SELL":
                            command_name = "later_up_close"
                            boundary = stop_price
                            left_margin = None
                    elif side == "BUY":
                        command_name = "later_down_buy"
                        boundary = stop_price
                        left_quantity = origianal_quantity
                        left_margin = left_quantity * boundary / leverage
                    elif side == "SELL":
                        command_name = "later_up_sell"
                        boundary = stop_price
                        left_quantity = origianal_quantity
                        left_margin = left_quantity * boundary / leverage
                elif order_type == "LIMIT":
                    if side == "BUY":
                        command_name = "book_buy"
                        boundary = price
                        left_quantity = origianal_quantity - executed_quantity
                        left_margin = left_quantity * boundary / leverage
                    elif side == "SELL":
                        command_name = "book_sell"
                        boundary = price
                        left_quantity = origianal_quantity - executed_quantity
                        left_margin = left_quantity * boundary / leverage
                else:
                    command_name = "other"
                    boundary = max(price, stop_price)
                    left_quantity = origianal_quantity - executed_quantity
                    left_margin = left_quantity * boundary / leverage

                self.account_state["open_orders"][symbol][order_id] = {
                    "command_name": command_name,
                    "boundary": boundary,
                    "left_margin": left_margin,
                }

            # when the order is filled
            if execution_type == "TRADE":

                asset_change = realized_profit - commission
                added_notional = last_filled_price * last_filled_quantity
                added_margin = added_notional / leverage
                added_margin_ratio = added_margin / wallet_balance

                with self.datalocks[1]:
                    df = self.trade_record
                    symbol_df = df[df["Symbol"] == symbol]
                    recorded_id_list = symbol_df["Order ID"].tolist()
                    does_record_exist = order_id in recorded_id_list
                    if does_record_exist:
                        mask_sr = symbol_df["Order ID"] == order_id
                        recorded_time = symbol_df.index[mask_sr][0]
                        recorded_value = symbol_df.loc[recorded_time, "Margin Ratio"]
                        new_value = recorded_value + added_margin_ratio
                        self.trade_record.loc[recorded_time, "Margin Ratio"] = new_value
                        with self.datalocks[2]:
                            last_asset = self.asset_trace.iloc[-1]
                            new_value = last_asset + asset_change
                            self.asset_trace.iloc[-1] = new_value
                            asset_trace_copy = self.asset_trace.copy()
                    else:
                        new_value = symbol
                        self.trade_record.loc[event_time, "Symbol"] = new_value
                        new_value = "sell" if side == "SELL" else "buy"
                        self.trade_record.loc[event_time, "Side"] = new_value
                        new_value = last_filled_price
                        self.trade_record.loc[event_time, "Fill Price"] = new_value
                        new_value = "maker" if is_maker else "taker"
                        self.trade_record.loc[event_time, "Role"] = new_value
                        new_value = added_margin_ratio
                        self.trade_record.loc[event_time, "Margin Ratio"] = new_value
                        new_value = order_id
                        self.trade_record.loc[event_time, "Order ID"] = new_value
                        with self.datalocks[2]:
                            last_asset = self.asset_trace.iloc[-1]
                            new_value = last_asset + asset_change
                            self.asset_trace[event_time] = new_value
                            self.asset_trace = self.asset_trace.sort_index()
                            asset_trace_copy = self.asset_trace.copy()
                    trade_record_copy = self.trade_record.copy()

                asset_trace_copy.to_pickle(self.workerpath + "/asset_trace.pickle")
                trade_record_copy.to_pickle(self.workerpath + "/trade_record.pickle")

        # ■■■■■ cancel conflicting orders ■■■■■

        self.cancel_conflicting_orders()

    def save_unrealized_changes(self, *args, **kwargs):
        with self.datalocks[0]:
            self.unrealized_changes = self.unrealized_changes.sort_index()
            self.unrealized_changes = self.unrealized_changes.astype(np.float32)
            unrealized_changes = self.unrealized_changes.copy()
        unrealized_changes.to_pickle(self.workerpath + "/unrealized_changes.pickle")

    def open_exchange(self, *args, **kwargs):
        symbol = self.viewing_symbol
        webbrowser.open(f"https://www.binance.com/en/futures/{symbol}")

    def open_futures_wallet_page(self, *args, **kwargs):
        webbrowser.open("https://www.binance.com/en/my/wallet/account/futures")

    def open_api_management_page(self, *args, **kwargs):
        webbrowser.open("https://www.binance.com/en/my/settings/api-management")

    def update_keys(self, *args, **kwargs):
        def job():
            return (
                self.root.comboBox_3.currentIndex(),
                self.root.lineEdit_4.text(),
                self.root.lineEdit_6.text(),
            )

        returned = self.root.undertake(job, True)

        new_keys = {}
        if returned[0] == 0:
            server = "real"
        elif returned[0] == 1:
            server = "testnet"
        new_keys["server"] = server
        new_keys["binance_api"] = returned[1]
        new_keys["binance_secret"] = returned[2]

        self.keys = new_keys

        filepath = self.workerpath + "/keys.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(new_keys, file, indent=4)

        self.api_requester.update_keys(new_keys)
        self.update_user_data_stream()

    def update_automation_settings(self, *args, **kwargs):

        # ■■■■■ get information about strategy ■■■■■

        index = self.root.undertake(lambda: self.root.comboBox_2.currentIndex(), True)
        strategy = self.root.strategy_tuples[index][0]
        self.automation_settings["strategy"] = strategy

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
                "이 전략으로는 자동 주문을 켜도 아무 일도 일어나지 않습니다.",
                ["확인"],
                False,
            ]
            self.root.ask(question)

        self.display_lines()

        # ■■■■■ is automation turned on ■■■■■

        is_checked = self.root.undertake(lambda: self.root.checkBox.isChecked(), True)

        if is_checked:

            if strategy == 0:
                question = [
                    "나만의 전략이 선택되어 있습니다.",
                    "직접 만든 전략을 사용하기 전에 스크립트가 잘 짜였는지 확인하세요. 만약 나만의 전략 스크립트가 비어 있다면 아무 일도"
                    " 일어나지 않습니다.",
                    ["확인"],
                    False,
                ]
                self.root.ask(question)

            elif strategy in (1, 2):
                question = [
                    "랜덤 주문 전략이 선택되어 있습니다.",
                    "랜덤 주문 전략이 켜진 상태로 자동 주문을 켜 놓으면 아무 시장에서 총 자산의 1/10000만큼씩 의미 없는"
                    " 거래를 반복하게 됩니다. 이 전략은 자동 주문 코드가 잘 작동하는지 확인하기 위한 용도로 만들어졌습니다. 오랫동안 켜"
                    " 놓으면 수수료가 많이 발생하니 조심하세요.",
                    ["확인"],
                    False,
                ]
                self.root.ask(question)

            if strategy == 0:
                strategy_details = self.root.strategist.details
            else:
                for strategy_tuple in self.root.strategy_tuples:
                    if strategy_tuple[0] == strategy:
                        strategy_details = strategy_tuple[2]
            is_fast_strategy = strategy_details[3]

            if not is_fast_strategy:
                current_moment = datetime.now(timezone.utc).replace(microsecond=0)
                current_moment = current_moment - timedelta(
                    seconds=current_moment.second % 10
                )
                count_start_time = current_moment - timedelta(hours=24)
                with self.root.collector.datalocks[0]:
                    df = self.root.collector.candle_data
                    cumulated_moments = len(df[count_start_time:].dropna())
                needed_moments = 24 * 60 * 60 / 10
                ratio = cumulated_moments / needed_moments
                if ratio < 1:
                    is_insufficient = True
                else:
                    is_insufficient = False

                if is_insufficient:
                    question = [
                        "데이터 누적률이 100%가 아닙니다.",
                        "저속 전략에서 자동 주문이 작동하려면 캔들 데이터의 지난 24시간 누적률이 100%여야 합니다. 자동 주문이"
                        " 켜져 있더라도 지난 24시간 누적률이 100%가 될 때까지는 아무 일도 일어나지 않습니다.",
                        ["확인"],
                        False,
                    ]
                    self.root.ask(question)

            self.automation_settings["should_transact"] = True

        else:

            self.automation_settings["should_transact"] = False

        # ■■■■■ save ■■■■■

        with open(
            self.workerpath + "/automation_settings.json", "w", encoding="utf8"
        ) as file:
            json.dump(self.automation_settings, file, indent=4)

    def display_range_information(self, *args, **kwargs):

        task_id = stop_flag.make("display_transaction_range_information")

        symbol = self.viewing_symbol

        range_start = self.root.undertake(
            lambda: self.root.plot_widget.getAxis("bottom").range[0], True
        )
        range_start = max(range_start, 0)
        range_start = datetime.fromtimestamp(range_start, tz=timezone.utc)

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        range_end = self.root.undertake(
            lambda: self.root.plot_widget.getAxis("bottom").range[1], True
        )
        if range_end < 0:
            # case when pyqtgraph passed negative value because it's too big
            range_end = 9223339636
        else:
            # maximum value available in pandas
            range_end = min(range_end, 9223339636)
        range_end = datetime.fromtimestamp(range_end, tz=timezone.utc)

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        range_length = range_end - range_start
        range_days = range_length.days
        range_hours, remains = divmod(range_length.seconds, 3600)
        range_minutes, remains = divmod(remains, 60)
        range_length_text = f"{range_days}일 {range_hours}시간 {range_minutes}분"

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        with self.datalocks[0]:
            unrealized_changes = self.unrealized_changes[range_start:range_end].copy()
        with self.datalocks[1]:
            trade_record = self.trade_record[range_start:range_end].copy()
        with self.datalocks[2]:
            asset_trace = self.asset_trace[range_start:range_end].copy()

        asset_changes = asset_trace.pct_change() + 1
        asset_changes = asset_changes.reindex(trade_record.index).fillna(value=1)
        symbol_mask = trade_record["Symbol"] == symbol

        # trade count
        total_change_count = len(asset_changes)
        symbol_change_count = len(asset_changes[symbol_mask])
        # trade volume
        if len(trade_record) > 0:
            total_margin_ratio = trade_record["Margin Ratio"].sum()
        else:
            total_margin_ratio = 0
        if len(trade_record[symbol_mask]) > 0:
            symbol_margin_ratio = trade_record[symbol_mask]["Margin Ratio"].sum()
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

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        range_down = self.root.undertake(
            lambda: self.root.plot_widget.getAxis("left").range[0], True
        )
        range_up = self.root.undertake(
            lambda: self.root.plot_widget.getAxis("left").range[1], True
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
        self.root.undertake(lambda t=text: self.root.label_8.setText(t), False)

    def display_lines(self, *args, **kwargs):

        periodic = kwargs.get("periodic", False)
        only_light_lines = kwargs.get("only_light_lines", False)

        if only_light_lines:
            task_start_time = datetime.now(timezone.utc)

        if not only_light_lines:
            task_id = stop_flag.make("display_transaction_lines")

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
                    if stop_flag.find("display_transaction_lines", task_id):
                        return
                with self.root.collector.datalocks[0]:
                    last_index = self.root.collector.candle_data.index[-1]
                    if last_index == before_moment:
                        break
                time.sleep(0.1)

        # ■■■■■ check strategy ■■■■■

        strategy = self.automation_settings["strategy"]

        if strategy == 0:
            strategy_details = self.root.strategist.details
        else:
            for strategy_tuple in self.root.strategy_tuples:
                if strategy_tuple[0] == strategy:
                    strategy_details = strategy_tuple[2]
        is_fast_strategy = strategy_details[3]

        # ■■■■■ get the data ■■■■■

        symbol = self.viewing_symbol

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
                    df = df.iloc[-2 * 10**5 :][[symbol]].copy()
                    candle_data = df

        with self.root.collector.datalocks[1]:
            before_chunk = self.root.collector.realtime_data_chunks[-2].copy()
            current_chunk = self.root.collector.realtime_data_chunks[-1].copy()
        realtime_data = np.concatenate((before_chunk, current_chunk))
        with self.root.collector.datalocks[2]:
            aggregate_trades = self.root.collector.aggregate_trades.copy()

        with self.datalocks[0]:
            unrealized_changes = self.unrealized_changes.copy()
        with self.datalocks[1]:
            trade_record = self.trade_record.copy()
        with self.datalocks[2]:
            asset_trace = self.asset_trace.copy()

        # ■■■■■ make indicators ■■■■■

        indicators_script = self.root.strategist.indicators_script
        compiled_indicators_script = compile(indicators_script, "<string>", "exec")

        if is_fast_strategy:
            observed_data = process_toss.apply(digitize.do, realtime_data)
            observed_data = observed_data.iloc[-3600 * 10 :]  # recent one hour
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
        if len(asset_trace) > 0:
            asset_trace[observed_until] = asset_trace.iloc[-1]

        # ■■■■■ draw ■■■■■

        # mark price
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            data_x = realtime_data["index"].astype(np.int64) / 10**9
            data_y = realtime_data[str((symbol, "Mark Price"))]
            mask = data_y != 0
            data_y = data_y[mask]
            data_x = data_x[mask]
            widget = self.root.transaction_lines["mark_price"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
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
            widget = self.root.transaction_lines["last_price"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
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
            widget = self.root.transaction_lines["last_volume"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
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
            widget = self.root.transaction_lines["book_tickers"][0]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

            data_x = realtime_data["index"].astype(np.int64) / 10**9
            data_y = realtime_data[str((symbol, "Best Ask Price"))]
            mask = data_y != 0
            data_y = data_y[mask]
            data_x = data_x[mask]
            widget = self.root.transaction_lines["book_tickers"][1]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

        # price indicators
        is_light_line = True if is_fast_strategy else False
        if (only_light_lines and is_light_line) or not only_light_lines:
            df = indicators[symbol]["Price"]
            data_x = df.index.to_numpy(dtype=np.int64) / 10**9
            if not is_fast_strategy:
                data_x += 5
            line_list = self.root.transaction_lines["price_indicators"]
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
                        if stop_flag.find("display_transaction_lines", task_id):
                            return
                    self.root.undertake(job, False)
                elif not only_light_lines:
                    if not only_light_lines:
                        if stop_flag.find("display_transaction_lines", task_id):
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
            widget = self.root.transaction_lines["price_movement"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
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
            widget = self.root.transaction_lines["close_price"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

        # wobbles
        is_light_line = False
        if (only_light_lines and is_light_line) or not only_light_lines:
            sr = candle_data[(symbol, "High")]
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.transaction_lines["wobbles"][0]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

            sr = candle_data[(symbol, "Low")]
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.transaction_lines["wobbles"][1]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
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
            for turn, widget in enumerate(self.root.transaction_lines["boundaries"]):
                if turn < len(boundaries):
                    boundary = boundaries[turn]
                    data_x = np.linspace(
                        first_moment.timestamp(), last_moment.timestamp(), num=1000
                    )
                    data_y = np.linspace(boundary, boundary, num=1000)
                    widget = self.root.transaction_lines["boundaries"][turn]

                    def job(widget=widget, data_x=data_x, data_y=data_y):
                        widget.setData(data_x, data_y)

                    if not only_light_lines:
                        if stop_flag.find("display_transaction_lines", task_id):
                            return
                    self.root.undertake(job, False)
                elif not only_light_lines:
                    if not only_light_lines:
                        if stop_flag.find("display_transaction_lines", task_id):
                            return
                    self.root.undertake(lambda w=widget: w.clear(), False)

        # trade volume indicators
        is_light_line = True if is_fast_strategy else False
        if (only_light_lines and is_light_line) or not only_light_lines:
            df = indicators[symbol]["Volume"]
            data_x = df.index.to_numpy(dtype=np.int64) / 10**9
            if not is_fast_strategy:
                data_x += 5
            line_list = self.root.transaction_lines["volume_indicators"]
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
                        if stop_flag.find("display_transaction_lines", task_id):
                            return
                    self.root.undertake(job, False)
                elif not only_light_lines:
                    if not only_light_lines:
                        if stop_flag.find("display_transaction_lines", task_id):
                            return
                    self.root.undertake(lambda w=widget: w.clear(), False)

        # trade volume
        is_light_line = False
        if (only_light_lines and is_light_line) or not only_light_lines:
            sr = candle_data[(symbol, "Volume")]
            sr = sr.fillna(value=0)
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.transaction_lines["volume"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

        # abstract indicators indicators
        is_light_line = True if is_fast_strategy else False
        if (only_light_lines and is_light_line) or not only_light_lines:
            df = indicators[symbol]["Abstract"]
            data_x = df.index.to_numpy(dtype=np.int64) / 10**9
            if not is_fast_strategy:
                data_x += 5
            line_list = self.root.transaction_lines["abstract_indicators"]
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
                        if stop_flag.find("display_transaction_lines", task_id):
                            return
                    self.root.undertake(job, False)
                elif not only_light_lines:
                    if not only_light_lines:
                        if stop_flag.find("display_transaction_lines", task_id):
                            return
                    self.root.undertake(lambda w=widget: w.clear(), False)

        # asset
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            data_x = asset_trace.index.to_numpy(dtype=np.int64) / 10**9
            data_y = asset_trace.to_numpy(dtype=np.float32)
            widget = self.root.transaction_lines["asset"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

        # asset with unrealized profit
        is_light_line = False
        if (only_light_lines and is_light_line) or not only_light_lines:
            if len(asset_trace) >= 2:
                sr = asset_trace.resample("10S").ffill()
            unrealized_changes_sr = unrealized_changes.reindex(sr.index)
            sr = sr * (1 + unrealized_changes_sr)
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9 + 5
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.transaction_lines["asset_with_unrealized_profit"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

        # buy and sell
        is_light_line = True
        if (only_light_lines and is_light_line) or not only_light_lines:
            df = trade_record.loc[trade_record["Symbol"] == symbol]
            df = df[df["Side"] == "sell"]
            sr = df["Fill Price"]
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.transaction_lines["sell"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

            df = trade_record.loc[trade_record["Symbol"] == symbol]
            df = df[df["Side"] == "buy"]
            sr = df["Fill Price"]
            data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
            data_y = sr.to_numpy(dtype=np.float32)
            widget = self.root.transaction_lines["buy"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
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
            widget = self.root.transaction_lines["entry_price"]

            def job(widget=widget, data_x=data_x, data_y=data_y):
                widget.setData(data_x, data_y)

            if not only_light_lines:
                if stop_flag.find("display_transaction_lines", task_id):
                    return
            self.root.undertake(job, False)

        # ■■■■■ record task duration ■■■■■

        if only_light_lines:
            duration = (datetime.now(timezone.utc) - task_start_time).total_seconds()
            remember_task_durations.add("display_light_lines", duration)

    def toggle_vertical_automation(self, *args, **kwargs):
        state = args[0]
        if state == QtCore.Qt.CheckState.Checked.value:
            self.root.plot_widget.setMouseEnabled(y=True)
            self.root.plot_widget_1.setMouseEnabled(y=True)
            self.root.plot_widget_4.setMouseEnabled(y=True)
            self.root.plot_widget_6.setMouseEnabled(y=True)
            self.root.plot_widget.enableAutoRange(y=False)
            self.root.plot_widget_1.enableAutoRange(y=False)
            self.root.plot_widget_4.enableAutoRange(y=False)
            self.root.plot_widget_6.enableAutoRange(y=False)
        else:
            self.root.plot_widget.setMouseEnabled(y=False)
            self.root.plot_widget_1.setMouseEnabled(y=False)
            self.root.plot_widget_4.setMouseEnabled(y=False)
            self.root.plot_widget_6.setMouseEnabled(y=False)
            self.root.plot_widget.enableAutoRange(y=True)
            self.root.plot_widget_1.enableAutoRange(y=True)
            self.root.plot_widget_4.enableAutoRange(y=True)
            self.root.plot_widget_6.enableAutoRange(y=True)

    def update_viewing_symbol(self, *args, **kwargs):
        def job():
            return self.root.comboBox_4.currentText()

        alias = self.root.undertake(job, True)
        symbol = self.root.alias_to_symbol[alias]
        self.viewing_symbol = symbol

        self.display_lines()
        self.display_asset_information()
        self.display_range_information()

    def display_asset_information(self, *args, **kwargs):

        # ■■■■■ is it the recent information? ■■■■■

        time_passed = datetime.now(timezone.utc) - self.account_state["observed_until"]
        if time_passed > timedelta(seconds=30):
            text = "키 또는 바이낸스 서버 연결에 문제가 있어 바이낸스 계정의 최신 정보를 알아내지 못함"
            self.root.undertake(lambda t=text: self.root.label_16.setText(t), False)
            return

        # ■■■■■ display the information ■■■■■

        price_precision = self.exchange_state["price_precisions"][self.viewing_symbol]
        position = self.account_state["positions"][self.viewing_symbol]
        if position["direction"] == "long":
            direction_text = "매수"
        elif position["direction"] == "short":
            direction_text = "매도"
        else:
            direction_text = "없음"
        margin_sum = 0
        for each_position in self.account_state["positions"].values():
            margin_sum += each_position["margin"]
        text = ""
        text += f"총 자산 ＄{round(self.account_state['wallet_balance'],4)}"
        text += "  ⦁  "
        text += f"투입 자산 ＄{round(position['margin'], 4)}/{round(margin_sum,4)}"
        text += "  ⦁  "
        text += f"방향 {direction_text}"
        text += "  ⦁  "
        text += f"평균 단가 ＄{round(position['entry_price'],price_precision)}"
        self.root.undertake(lambda t=text: self.root.label_16.setText(t), False)

    def transact_fast(self, *args, **kwargs):

        # stop if it's not connected to the internet
        if not check_internet.connected():
            return

        # stop if the automation is turned off
        if not self.automation_settings["should_transact"]:
            return

        # get strategy details
        strategy = self.automation_settings["strategy"]

        if strategy == 0:
            strategy_details = self.root.strategist.details
        else:
            for strategy_tuple in self.root.strategy_tuples:
                if strategy_tuple[0] == strategy:
                    strategy_details = strategy_tuple[2]

        # determine if should keep on going
        is_fast_strategy = strategy_details[3]
        if not is_fast_strategy:
            return

        is_working_strategy = strategy_details[0]
        if not is_working_strategy:
            return

        # play the progress bar
        def job():
            start_time = datetime.now(timezone.utc)
            self.root.undertake(lambda: self.root.progressBar_2.setValue(1000), False)
            passed_time = timedelta(seconds=0)
            while passed_time < timedelta(milliseconds=500):
                passed_time = datetime.now(timezone.utc) - start_time
                time.sleep(0.01)
            self.root.undertake(lambda: self.root.progressBar_2.setValue(0), False)

        thread_toss.apply_async(job)

        def job():

            # ■■■■■ task start time ■■■■■

            task_start_time = datetime.now(timezone.utc)

            # ■■■■■ moment ■■■■■

            current_time = datetime.now(timezone.utc)
            moment_timestamp = ball.floor(current_time.timestamp(), 1)
            current_moment = datetime.fromtimestamp(moment_timestamp, tz=timezone.utc)

            # ■■■■■ get the realtime data ■■■■■

            with self.root.collector.datalocks[1]:
                before_chunk = self.root.collector.realtime_data_chunks[-2].copy()
                current_chunk = self.root.collector.realtime_data_chunks[-1].copy()
            realtime_data = np.concatenate((before_chunk, current_chunk))
            realtime_data = realtime_data[-10000:]

            # ■■■■■ make indicators ■■■■■

            indicators_script = self.root.strategist.indicators_script
            compiled_indicators_script = compile(indicators_script, "<string>", "exec")

            observed_data = process_toss.apply(digitize.do, realtime_data)
            observed_data = observed_data.iloc[-3600 * 10 :]  # recent one hour
            indicators = process_toss.apply(
                make_indicators.do,
                observed_data=observed_data,
                strategy=strategy,
                compiled_custom_script=compiled_indicators_script,
            )

            # ■■■■■ make decision ■■■■■

            current_observed_data = observed_data.to_records()[-1]
            current_indicators = indicators.to_records()[-1]
            decision_script = self.root.strategist.decision_script
            compiled_decision_script = compile(decision_script, "<string>", "exec")

            decision = decide.choose(
                current_moment=current_moment,
                current_observed_data=current_observed_data,
                current_indicators=current_indicators,
                strategy=strategy,
                account_state=copy.deepcopy(self.account_state),
                scribbles=self.scribbles,
                compiled_custom_script=compiled_decision_script,
            )

            # ■■■■■ record task duration ■■■■■

            duration = datetime.now(timezone.utc) - task_start_time
            duration = duration.total_seconds()
            remember_task_durations.add("decide_transacting_fast", duration)

            # ■■■■■ place order ■■■■■

            self.place_order(decision)

        for _ in range(10):
            thread_toss.apply_async(job)
            time.sleep(0.1)

    def transact_slow(self, *args, **kwargs):

        # ■■■■■ stop if internet connection is not present ■■■■

        if not check_internet.connected():
            return

        # ■■■■■ stop if the automation is turned off ■■■■■

        if not self.automation_settings["should_transact"]:
            return

        # ■■■■■ get strategy details ■■■■■

        strategy = self.automation_settings["strategy"]

        if strategy == 0:
            strategy_details = self.root.strategist.details
        else:
            for strategy_tuple in self.root.strategy_tuples:
                if strategy_tuple[0] == strategy:
                    strategy_details = strategy_tuple[2]

        # ■■■■■ determine if should keep on going ■■■■■

        is_fast_strategy = strategy_details[3]
        if is_fast_strategy:
            return

        is_working_strategy = strategy_details[0]
        if not is_working_strategy:
            return

        # ■■■■■ play the progress bar ■■■■■

        is_cycle_done = False

        def job():
            start_time = datetime.now(timezone.utc)
            passed_time = timedelta(seconds=0)
            while passed_time < timedelta(seconds=10):
                passed_time = datetime.now(timezone.utc) - start_time
                if not is_cycle_done:
                    new_value = int(passed_time / timedelta(seconds=10) * 1000)
                else:
                    before_value = self.root.undertake(
                        lambda: self.root.progressBar_2.value(), True
                    )
                    remaining = 1000 - before_value
                    new_value = before_value + math.ceil(remaining * 0.2)

                def job(new_value=new_value):
                    self.root.progressBar_2.setValue(new_value)

                self.root.undertake(job, False)
                time.sleep(0.01)

            self.root.undertake(lambda: self.root.progressBar_2.setValue(0), False)

        thread_toss.apply_async(job)

        # ■■■■■ moment ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        # ■■■■■ check if the data exists ■■■■■

        with self.root.collector.datalocks[0]:
            if len(self.root.collector.candle_data) == 0:
                # case when the app is executed for the first time
                return

        # ■■■■■ wait for the latest data to be added ■■■■■

        for _ in range(50):
            with self.root.collector.datalocks[0]:
                last_index = self.root.collector.candle_data.index[-1]
                if last_index == before_moment:
                    break
            time.sleep(0.1)

        # ■■■■■ stop if the accumulation rate is not 100% ■■■■■

        count_start_time = current_moment - timedelta(hours=24)

        with self.root.collector.datalocks[0]:
            df = self.root.collector.candle_data
            cumulated_moments = len(df[count_start_time:].dropna())
        needed_moments = 24 * 60 * 60 / 10
        ratio = cumulated_moments / needed_moments
        if ratio < 1:
            is_cycle_done = True
            return

        # ■■■■■ get the candle data ■■■■■

        slice_from = datetime.now(timezone.utc) - timedelta(days=7)
        with self.root.collector.datalocks[0]:
            df = self.root.collector.candle_data
            partial_candle_data = df[slice_from:].copy()

        # ■■■■■ make decision ■■■■■

        indicators_script = self.root.strategist.indicators_script
        compiled_indicators_script = compile(indicators_script, "<string>", "exec")

        indicators = process_toss.apply(
            make_indicators.do,
            observed_data=partial_candle_data,
            strategy=strategy,
            compiled_custom_script=compiled_indicators_script,
        )

        current_observed_data = partial_candle_data.to_records()[-1]
        current_indicators = indicators.to_records()[-1]
        decision_script = self.root.strategist.decision_script
        compiled_decision_script = compile(decision_script, "<string>", "exec")

        decision = decide.choose(
            current_moment=current_moment,
            current_observed_data=current_observed_data,
            current_indicators=current_indicators,
            strategy=strategy,
            account_state=copy.deepcopy(self.account_state),
            scribbles=self.scribbles,
            compiled_custom_script=compiled_decision_script,
        )

        # ■■■■■ record task duration ■■■■■

        is_cycle_done = True
        duration = (datetime.now(timezone.utc) - current_moment).total_seconds()
        remember_task_durations.add("decide_transacting_slow", duration)

        # ■■■■■ place order ■■■■■

        self.place_order(decision)

    def display_day_range(self, *args, **kwargs):
        range_start = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
        range_end = datetime.now(timezone.utc).timestamp()
        widget = self.root.plot_widget

        def job(range_start=range_start, range_end=range_end):
            widget.setXRange(range_start, range_end)

        self.root.undertake(job, False)

    def open_testnet_exchange(self, *args, **kwargs):
        symbol = self.viewing_symbol
        webbrowser.open(f"https://testnet.binancefuture.com/en/futures/{symbol}")

    def match_graph_range(self, *args, **kwargs):
        range_start = self.root.undertake(
            lambda: self.root.plot_widget_2.getAxis("bottom").range[0], True
        )
        range_end = self.root.undertake(
            lambda: self.root.plot_widget_2.getAxis("bottom").range[1], True
        )
        widget = self.root.plot_widget

        def job(range_start=range_start, range_end=range_end):
            widget.setXRange(range_start, range_end, padding=0)

        self.root.undertake(job, False)

    def update_mode_settings(self, *args, **kwargs):

        desired_leverage = self.root.undertake(lambda: self.root.spinBox.value(), True)
        self.mode_settings["desired_leverage"] = desired_leverage

        # ■■■■■ save ■■■■■

        with open(
            self.workerpath + "/mode_settings.json", "w", encoding="utf8"
        ) as file:
            json.dump(self.mode_settings, file, indent=4)

    def watch_binance(self, *args, **kwargs):

        # ■■■■■ check internet connection ■■■■■

        if not check_internet.connected():
            return

        # ■■■■■ moment ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        # ■■■■■ request exchange information ■■■■■

        payload = {}
        response = self.api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload=payload,
        )
        about_exchange = response

        # ■■■■■ remember exchange information ■■■■■

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

        # ■■■■■ request account information ■■■■■

        try:
            payload = {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
            response = self.api_requester.binance(
                http_method="GET",
                path="/fapi/v2/account",
                payload=payload,
            )
            about_account = response
        except ApiRequestError:
            # when the key is not ready
            return

        about_open_orders = {}

        def job(symbol):
            payload = {
                "symbol": symbol,
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
            response = self.api_requester.binance(
                http_method="GET",
                path="/fapi/v1/openOrders",
                payload=payload,
            )
            about_open_orders[symbol] = response

        thread_toss.map(job, standardize.get_basics()["target_symbols"])

        # ■■■■■ update account state ■■■■■

        # observed until
        self.account_state["observed_until"] = current_moment

        # wallet_balance
        for about_asset in about_account["assets"]:
            if about_asset["asset"] == "USDT":
                break
        wallet_balance = float(about_asset["walletBalance"])
        self.account_state["wallet_balance"] = wallet_balance

        # positions
        for symbol in standardize.get_basics()["target_symbols"]:
            for about_position in about_account["positions"]:
                if about_position["symbol"] == symbol:
                    break

            if float(about_position["notional"]) > 0:
                direction = "long"
            elif float(about_position["notional"]) == 0:
                direction = "none"
            elif float(about_position["notional"]) < 0:
                direction = "short"

            entry_price = float(about_position["entryPrice"])
            update_time = int(float(about_position["updateTime"]) / 1000)
            update_time = datetime.fromtimestamp(update_time, tz=timezone.utc)
            leverage = int(about_position["leverage"])
            amount = float(about_position["positionAmt"])
            margin = abs(amount) * entry_price / leverage

            self.account_state["positions"][symbol]["margin"] = margin
            self.account_state["positions"][symbol]["direction"] = direction
            self.account_state["positions"][symbol]["entry_price"] = entry_price
            self.account_state["positions"][symbol]["update_time"] = update_time

        # open orders
        open_orders = {}
        for symbol in standardize.get_basics()["target_symbols"]:
            open_orders[symbol] = {}

        for symbol in standardize.get_basics()["target_symbols"]:

            for about_position in about_account["positions"]:
                if about_position["symbol"] == symbol:
                    break

            leverage = int(about_position["leverage"])

            for about_open_order in about_open_orders[symbol]:

                order_id = about_open_order["orderId"]
                order_type = about_open_order["type"]

                side = about_open_order["side"]
                close_position = about_open_order["closePosition"]

                price = float(about_open_order["price"])
                stop_price = float(about_open_order["stopPrice"])
                origianal_quantity = float(about_open_order["origQty"])
                executed_quantity = float(about_open_order["executedQty"])

                if order_type == "STOP_MARKET":
                    if close_position:
                        if side == "BUY":
                            command_name = "later_up_close"
                            boundary = stop_price
                            left_margin = None
                        elif side == "SELL":
                            command_name = "later_down_close"
                            boundary = stop_price
                            left_margin = None
                    elif side == "BUY":
                        command_name = "later_up_buy"
                        boundary = stop_price
                        left_quantity = origianal_quantity
                        left_margin = left_quantity * boundary / leverage
                    elif side == "SELL":
                        command_name = "later_down_sell"
                        boundary = stop_price
                        left_quantity = origianal_quantity
                        left_margin = left_quantity * boundary / leverage
                elif order_type == "TAKE_PROFIT_MARKET":
                    if close_position:
                        if side == "BUY":
                            command_name = "later_down_close"
                            boundary = stop_price
                            left_margin = None
                        elif side == "SELL":
                            command_name = "later_up_close"
                            boundary = stop_price
                            left_margin = None
                    elif side == "BUY":
                        command_name = "later_down_buy"
                        boundary = stop_price
                        left_quantity = origianal_quantity
                        left_margin = left_quantity * boundary / leverage
                    elif side == "SELL":
                        command_name = "later_up_sell"
                        boundary = stop_price
                        left_quantity = origianal_quantity
                        left_margin = left_quantity * boundary / leverage
                elif order_type == "LIMIT":
                    if side == "BUY":
                        command_name = "book_buy"
                        boundary = price
                        left_quantity = origianal_quantity - executed_quantity
                        left_margin = left_quantity * boundary / leverage
                    elif side == "SELL":
                        command_name = "book_sell"
                        boundary = price
                        left_quantity = origianal_quantity - executed_quantity
                        left_margin = left_quantity * boundary / leverage
                else:
                    command_name = "other"
                    boundary = max(price, stop_price)
                    left_quantity = origianal_quantity - executed_quantity
                    left_margin = left_quantity * boundary / leverage

                open_orders[symbol][order_id] = {
                    "command_name": command_name,
                    "boundary": boundary,
                    "left_margin": left_margin,
                }

        self.account_state["open_orders"] = open_orders

        # ■■■■■ update hidden state ■■■■■

        for symbol in standardize.get_basics()["target_symbols"]:

            for about_position in about_account["positions"]:
                if about_position["symbol"] == symbol:
                    break
            leverage = int(about_position["leverage"])
            self.hidden_state["leverages"][symbol] = leverage

        # ■■■■■ record unrealized change ■■■■■

        for about_asset in about_account["assets"]:
            if about_asset["asset"] == "USDT":
                break
        # walletBalance에 미실현 수익은 포함되지 않음
        wallet_balance = float(about_asset["walletBalance"])
        unrealized_profit = float(about_asset["unrealizedProfit"])
        unrealized_change = unrealized_profit / wallet_balance

        with self.datalocks[0]:
            self.unrealized_changes[before_moment] = unrealized_change

        # ■■■■■ make an asset trace if it's blank ■■■■■

        if len(self.asset_trace) == 0:
            for about_asset in about_account["assets"]:
                if about_asset["asset"] == "USDT":
                    break
            wallet_balance = float(about_asset["walletBalance"])
            with self.datalocks[2]:
                current_time = datetime.now(timezone.utc)
                self.asset_trace[current_time] = wallet_balance
                self.asset_trace.to_pickle(self.workerpath + "/asset_trace.pickle")

        # ■■■■■ when the wallet balance changed for no good reason ■■■■■

        for about_asset in about_account["assets"]:
            if about_asset["asset"] == "USDT":
                break
        wallet_balance = float(about_asset["walletBalance"])
        if abs(wallet_balance - self.asset_trace.iloc[-1]) / wallet_balance > 10**-9:
            # when the difference is bigger than one billionth
            # referal fee, funding fee, wallet transfer, ect..
            with self.datalocks[2]:
                current_time = datetime.now(timezone.utc)
                self.asset_trace[current_time] = wallet_balance
                self.asset_trace.to_pickle(self.workerpath + "/asset_trace.pickle")
        else:
            # when the difference is small enough to consider as an numeric error
            with self.datalocks[2]:
                self.asset_trace.iloc[-1] = wallet_balance

        # ■■■■■ correct mode of the account market if automation is turned on ■■■■■

        if self.automation_settings["should_transact"]:

            def job(symbol):
                for about_position in about_account["positions"]:
                    if about_position["symbol"] == symbol:
                        break
                leverage = int(about_position["leverage"])

                if leverage != self.mode_settings["desired_leverage"]:

                    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                    payload = {
                        "symbol": symbol,
                        "timestamp": timestamp,
                        "leverage": self.mode_settings["desired_leverage"],
                    }
                    self.api_requester.binance(
                        http_method="POST",
                        path="/fapi/v1/leverage",
                        payload=payload,
                    )

            thread_toss.map(job, standardize.get_basics()["target_symbols"])

            def job(symbol):

                for about_position in about_account["positions"]:
                    if about_position["symbol"] == symbol:
                        break

                isolated = about_position["isolated"]
                notional = float(about_position["notional"])

                if isolated:

                    # close position if exists
                    if notional != 0:
                        decision = {
                            symbol: {
                                "now_close": {},
                            },
                        }
                        self.place_order(decision)

                    # change to crossed margin mode
                    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                    payload = {
                        "symbol": symbol,
                        "timestamp": timestamp,
                        "marginType": "CROSSED",
                    }
                    self.api_requester.binance(
                        http_method="POST",
                        path="/fapi/v1/marginType",
                        payload=payload,
                    )

            thread_toss.map(job, standardize.get_basics()["target_symbols"])

            try:
                timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                payload = {
                    "timestamp": timestamp,
                    "multiAssetsMargin": "false",
                }
                self.api_requester.binance(
                    http_method="POST",
                    path="/fapi/v1/multiAssetsMargin",
                    payload=payload,
                )
            except ApiRequestError:
                pass

            try:
                timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                payload = {
                    "timestamp": timestamp,
                    "dualSidePosition": "false",
                }
                self.api_requester.binance(
                    http_method="POST",
                    path="/fapi/v1/positionSide/dual",
                    payload=payload,
                )
            except ApiRequestError:
                pass

    def place_order(self, *args, **kwargs):

        task_start_time = datetime.now(timezone.utc)

        decision = args[0]

        # cancel_all
        # now_close
        # now_buy
        # now_sell
        # later_up_close
        # later_down_close
        # later_up_buy
        # later_down_buy
        # later_up_sell
        # later_down_sell
        # book_buy
        # book_sell

        # ■■■■■ prepare orders ■■■■■

        cancel_orders = []
        new_orders = []

        for symbol in standardize.get_basics()["target_symbols"]:

            if symbol not in decision.keys():
                continue

            with self.root.collector.datalocks[2]:
                ar = self.root.collector.aggregate_trades[-10000:].copy()
            temp_ar = ar[str((symbol, "Price"))]
            temp_ar = temp_ar[temp_ar != 0]
            current_price = float(temp_ar[-1])

            leverage = self.hidden_state["leverages"][symbol]
            maximum_quantity = self.exchange_state["maximum_quantities"][symbol]
            minimum_notional = self.exchange_state["minimum_notionals"][symbol]
            price_precision = self.exchange_state["price_precisions"][symbol]
            quantity_precision = self.exchange_state["quantity_precisions"][symbol]

            if "cancel_all" in decision[symbol]:
                cancel_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                }
                cancel_orders.append(cancel_order)

            if "now_close" in decision[symbol]:
                command = decision[symbol]["now_close"]
                quantity = maximum_quantity
                if self.account_state["positions"][symbol]["direction"] == "long":
                    side = "SELL"
                elif self.account_state["positions"][symbol]["direction"] == "short":
                    side = "BUY"
                else:
                    raise ValueError("There is no position to close")
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "MARKET",
                    "side": side,
                    "quantity": quantity,
                    "reduceOnly": True,
                }
                new_orders.append(new_order)

            if "now_buy" in decision[symbol]:
                command = decision[symbol]["now_buy"]
                notional = max(minimum_notional, command["margin"] * leverage)
                quantity = min(maximum_quantity, notional / current_price)
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "MARKET",
                    "side": "BUY",
                    "quantity": ball.ceil(quantity, quantity_precision),
                }
                new_orders.append(new_order)

            if "now_sell" in decision[symbol]:
                command = decision[symbol]["now_sell"]
                notional = max(minimum_notional, command["margin"] * leverage)
                quantity = min(maximum_quantity, notional / current_price)
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "MARKET",
                    "side": "SELL",
                    "quantity": ball.ceil(quantity, quantity_precision),
                }
                new_orders.append(new_order)

            if "later_up_close" in decision[symbol]:
                command = decision[symbol]["later_up_close"]
                if self.account_state["positions"][symbol]["direction"] == "long":
                    new_order_side = "SELL"
                    new_order_type = "TAKE_PROFIT_MARKET"
                elif self.account_state["positions"][symbol]["direction"] == "short":
                    new_order_side = "BUY"
                    new_order_type = "STOP_MARKET"
                else:
                    raise ValueError("There is no position to close")
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": new_order_type,
                    "side": new_order_side,
                    "stopPrice": round(command["boundary"], price_precision),
                    "closePosition": True,
                }
                new_orders.append(new_order)

            if "later_down_close" in decision[symbol]:
                command = decision[symbol]["later_down_close"]
                if self.account_state["positions"][symbol]["direction"] == "long":
                    new_order_side = "SELL"
                    new_order_type = "STOP_MARKET"
                elif self.account_state["positions"][symbol]["direction"] == "short":
                    new_order_side = "BUY"
                    new_order_type = "TAKE_PROFIT_MARKET"
                else:
                    raise ValueError("There is no position to close")
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": new_order_type,
                    "side": new_order_side,
                    "stopPrice": round(command["boundary"], price_precision),
                    "closePosition": True,
                }
                new_orders.append(new_order)

            if "later_up_buy" in decision[symbol]:
                command = decision[symbol]["later_up_buy"]
                notional = max(minimum_notional, command["margin"] * leverage)
                boundary = command["boundary"]
                quantity = min(maximum_quantity, notional / boundary)
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "STOP_MARKET",
                    "side": "BUY",
                    "quantity": ball.ceil(quantity, quantity_precision),
                    "stopPrice": round(boundary, price_precision),
                }
                new_orders.append(new_order)

            if "later_down_buy" in decision[symbol]:
                command = decision[symbol]["later_down_buy"]
                notional = max(minimum_notional, command["margin"] * leverage)
                boundary = command["boundary"]
                quantity = min(maximum_quantity, notional / boundary)
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "TAKE_PROFIT_MARKET",
                    "side": "BUY",
                    "quantity": ball.ceil(quantity, quantity_precision),
                    "stopPrice": round(boundary, price_precision),
                }
                new_orders.append(new_order)

            if "later_up_sell" in decision[symbol]:
                command = decision[symbol]["later_up_sell"]
                notional = max(minimum_notional, command["margin"] * leverage)
                boundary = command["boundary"]
                quantity = min(maximum_quantity, notional / boundary)
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "TAKE_PROFIT_MARKET",
                    "side": "SELL",
                    "quantity": ball.ceil(quantity, quantity_precision),
                    "stopPrice": round(boundary, price_precision),
                }
                new_orders.append(new_order)

            if "later_down_sell" in decision[symbol]:
                command = decision[symbol]["later_down_sell"]
                notional = max(minimum_notional, command["margin"] * leverage)
                boundary = command["boundary"]
                quantity = min(maximum_quantity, notional / boundary)
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "STOP_MARKET",
                    "side": "SELL",
                    "quantity": ball.ceil(quantity, quantity_precision),
                    "stopPrice": round(boundary, price_precision),
                }
                new_orders.append(new_order)

            if "book_buy" in decision[symbol]:
                command = decision[symbol]["book_buy"]
                notional = max(minimum_notional, command["margin"] * leverage)
                boundary = command["boundary"]
                quantity = min(maximum_quantity, notional / boundary)
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "LIMIT",
                    "side": "BUY",
                    "quantity": ball.ceil(quantity, quantity_precision),
                    "price": round(boundary, price_precision),
                    "timeInForce": "GTC",
                }
                new_orders.append(new_order)

            if "book_sell" in decision[symbol]:
                command = decision[symbol]["book_sell"]
                notional = max(minimum_notional, command["margin"] * leverage)
                boundary = command["boundary"]
                quantity = min(maximum_quantity, notional / boundary)
                new_order = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": symbol,
                    "type": "LIMIT",
                    "side": "SELL",
                    "quantity": ball.ceil(quantity, quantity_precision),
                    "price": round(boundary, price_precision),
                    "timeInForce": "GTC",
                }
                new_orders.append(new_order)

        # ■■■■■ actually place orders ■■■■■

        for new_order in new_orders:

            payload = new_order

            def job(payload=payload):
                self.api_requester.binance(
                    http_method="POST",
                    path="/fapi/v1/order",
                    payload=payload,
                )

            thread_toss.apply_async(job)

        for cancelorder in cancel_orders:

            payload = cancelorder

            def job(payload=payload):
                self.api_requester.binance(
                    http_method="DELETE",
                    path="/fapi/v1/allOpenOrders",
                    payload=payload,
                )

            thread_toss.apply_async(job)

        # ■■■■■ record task duration ■■■■■

        duration = datetime.now(timezone.utc) - task_start_time
        duration = duration.total_seconds()
        remember_task_durations.add("place_order", duration)

    def cancel_symbol_orders(self, *args, **kwargs):
        symbol = self.viewing_symbol
        decision = {
            symbol: {
                "cancel_all": {},
            },
        }
        self.place_order(decision)

    def cancel_conflicting_orders(self, *args, **kwargs):

        if not self.automation_settings["should_transact"]:
            return

        conflicting_order_tuples = []
        for symbol in standardize.get_basics()["target_symbols"]:
            symbol_open_orders = self.account_state["open_orders"][symbol]
            groups_by_command = {}
            for order_id, open_order_state in symbol_open_orders.items():
                command_name = open_order_state["command_name"]
                if command_name not in groups_by_command.keys():
                    groups_by_command[command_name] = [order_id]
                else:
                    groups_by_command[command_name].append(order_id)
            for command_name, group in groups_by_command.items():
                if command_name == "other":
                    for order_id in group:
                        conflicting_order_tuples.append((symbol, order_id))
                elif len(group) > 1:
                    latest_id = max(group)
                    for order_id in group:
                        if order_id != latest_id:
                            conflicting_order_tuples.append((symbol, order_id))

        for conflicting_order_tuple in conflicting_order_tuples:

            payload = {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "symbol": conflicting_order_tuple[0],
                "orderId": conflicting_order_tuple[1],
            }

            def job(payload=payload):
                try:
                    self.api_requester.binance(
                        http_method="DELETE",
                        path="/fapi/v1/order",
                        payload=payload,
                    )
                except ApiRequestError:
                    pass

            thread_toss.apply_async(job)
