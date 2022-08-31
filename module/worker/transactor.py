from datetime import datetime, timedelta, timezone
import json
import os
import time
import webbrowser
import math
import re
import pickle
import copy
import logging

import pandas as pd
import numpy as np
import getmac

from module import core
from module import process_toss
from module import thread_toss
from module.worker import collector
from module.worker import strategist
from module.instrument.api_requester import ApiRequester
from module.instrument.api_streamer import ApiStreamer
from module.instrument.api_request_error import ApiRequestError
from module.recipe import decide
from module.recipe import make_indicators
from module.recipe import ball
from module.recipe import stop_flag
from module.recipe import check_internet
from module.recipe import user_settings
from module.recipe import remember_task_durations
from module.recipe import standardize
from module.recipe import datalocks


class Transactor:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = user_settings.get_app_settings()["datapath"] + "/transactor"
        os.makedirs(self.workerpath, exist_ok=True)

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {
            "maximum_quantities": {},
            "minimum_notionals": {},
            "price_precisions": {},
            "quantity_precisions": {},
            "maximum_leverages": {},
            "leverages": {},
        }

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.viewing_symbol = user_settings.get_data_settings()["target_symbols"][0]
        self.should_draw_frequently = True

        self.account_state = standardize.account_state()

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
            core.window.undertake(
                lambda s=state: core.window.checkBox.setChecked(s), False
            )
            strategy_index = read_data["strategy_index"]
            core.window.undertake(
                lambda i=strategy_index: core.window.comboBox_2.setCurrentIndex(i),
                False,
            )
        except FileNotFoundError:
            self.automation_settings = {
                "strategy_index": 0,
                "should_transact": False,
            }

        try:
            filepath = self.workerpath + "/mode_settings.json"
            with open(filepath, "r", encoding="utf8") as file:
                read_data = json.load(file)
            self.mode_settings = read_data
            new_value = read_data["desired_leverage"]
            core.window.undertake(
                lambda n=new_value: core.window.spinBox.setValue(n), False
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
            core.window.undertake(
                lambda t=text: core.window.lineEdit_4.setText(t), False
            )
            text = keys["binance_secret"]
            core.window.undertake(
                lambda t=text: core.window.lineEdit_6.setText(t), False
            )
            self.keys = keys
            self.api_requester.update_keys(keys)
        except FileNotFoundError:
            self.keys = {
                "binance_api": "",
                "binance_secret": "",
            }

        try:
            filepath = self.workerpath + "/unrealized_changes.pickle"
            self.unrealized_changes = pd.read_pickle(filepath)
            self.unrealized_changes = self.unrealized_changes.sort_index()
            self.unrealized_changes = self.unrealized_changes.astype(np.float32)
        except FileNotFoundError:
            self.unrealized_changes = standardize.unrealized_changes()

        try:
            filepath = self.workerpath + "/asset_record.pickle"
            self.asset_record = pd.read_pickle(filepath)
            self.asset_record = self.asset_record.sort_index()
        except FileNotFoundError:
            self.asset_record = standardize.asset_record()

        try:
            filepath = self.workerpath + "/auto_order_record.pickle"
            self.auto_order_record = pd.read_pickle(filepath)
            self.auto_order_record = self.auto_order_record.sort_index()
        except FileNotFoundError:
            self.auto_order_record = pd.DataFrame(
                columns=[
                    "Symbol",
                    "Order ID",
                    "Net Profit",
                ],
                index=pd.DatetimeIndex([], tz="UTC"),
            )

        # ■■■■■ repetitive schedules ■■■■■

        core.window.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
            kwargs={"only_light_lines": True, "frequent": True},
        )
        core.window.scheduler.add_job(
            self.display_asset_information,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.display_range_information,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.cancel_conflicting_orders,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
            kwargs={"periodic": True, "frequent": True},
        )
        core.window.scheduler.add_job(
            self.move_view_range,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.perform_transaction,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.save_scribbles,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.watch_binance,
            trigger="cron",
            second="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.update_user_data_stream,
            trigger="cron",
            minute="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.save_unrealized_changes,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.pay_fees,
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

        connected_functions = [
            lambda: self.update_user_data_stream(),
            lambda: self.watch_binance(),
        ]
        check_internet.add_connected_functions(connected_functions)

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

            asset_token = user_settings.get_data_settings()["asset_token"]

            if asset_token in [about_asset["a"] for about_asset in about_assets]:
                for about_asset in about_assets:
                    asset_name = about_asset["a"]
                    if asset_name == asset_token:
                        break

                wallet_balance = float(about_asset["wb"])
                self.wallet_balance_state = wallet_balance

            if "BOTH" in [about_position["ps"] for about_position in about_positions]:
                for about_position in about_positions:
                    position_side = about_position["ps"]
                    if position_side == "BOTH":
                        break

                target_symbols = user_settings.get_data_settings()["target_symbols"]
                if about_position["s"] not in target_symbols:
                    return

                symbol = about_position["s"]
                amount = float(about_position["pa"])
                entry_price = float(about_position["ep"])

                leverage = self.secret_memory["leverages"][symbol]
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

            target_symbols = user_settings.get_data_settings()["target_symbols"]
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
            leverage = self.secret_memory["leverages"][symbol]
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
                net_profit = realized_profit - commission
                added_notional = last_filled_price * last_filled_quantity
                added_margin = added_notional / leverage
                added_margin_ratio = added_margin / wallet_balance

                with datalocks.hold("transactor_asset_record"):
                    df = self.asset_record
                    symbol_df = df[df["Symbol"] == symbol]
                    recorded_id_list = symbol_df["Order ID"].tolist()
                    does_record_exist = order_id in recorded_id_list
                    last_index = self.asset_record.index[-1]
                    if does_record_exist:
                        mask_sr = symbol_df["Order ID"] == order_id
                        recorded_time = symbol_df.index[mask_sr][0]
                        recorded_value = symbol_df.loc[recorded_time, "Margin Ratio"]
                        new_value = recorded_value + added_margin_ratio
                        self.asset_record.loc[recorded_time, "Margin Ratio"] = new_value
                        last_asset = self.asset_record.loc[last_index, "Result Asset"]
                        new_value = last_asset + net_profit
                        self.asset_record.loc[last_index, "Result Asset"] = new_value
                    else:
                        new_value = symbol
                        self.asset_record.loc[event_time, "Symbol"] = new_value
                        new_value = "sell" if side == "SELL" else "buy"
                        self.asset_record.loc[event_time, "Side"] = new_value
                        new_value = last_filled_price
                        self.asset_record.loc[event_time, "Fill Price"] = new_value
                        new_value = "maker" if is_maker else "taker"
                        self.asset_record.loc[event_time, "Role"] = new_value
                        new_value = added_margin_ratio
                        self.asset_record.loc[event_time, "Margin Ratio"] = new_value
                        new_value = order_id
                        self.asset_record.loc[event_time, "Order ID"] = new_value
                        last_asset = self.asset_record.loc[last_index, "Result Asset"]
                        new_value = last_asset + net_profit
                        self.asset_record.loc[event_time, "Result Asset"] = new_value
                        self.asset_record.loc[event_time, "Cause"] = "trade"
                        self.asset_record = self.asset_record.sort_index()
                    filepath = self.workerpath + "/asset_record.pickle"
                    self.asset_record.to_pickle(filepath)

                with datalocks.hold("transactor_auto_order_record"):
                    df = self.auto_order_record
                    symbol_df = df[df["Symbol"] == symbol]
                    unique_order_ids = symbol_df["Order ID"].unique()
                    if order_id in unique_order_ids:
                        mask_sr = symbol_df["Order ID"] == order_id
                        index = symbol_df.index[mask_sr][0]
                        self.auto_order_record.loc[index, "Net Profit"] += net_profit
                        filepath = self.workerpath + "/auto_order_record.pickle"
                        self.auto_order_record.to_pickle(filepath)

                if order_id in unique_order_ids:
                    strategy_index = self.automation_settings["strategy_index"]
                    strategy = strategist.me.strategies[strategy_index]
                    fee_address = strategy["fee_address"]
                    payload = {
                        "solsolPasscode": "SBJyXScaIEIteBPcqpMTMAG3T6B75rb4",
                        "deviceIdentifier": getmac.get_mac_address(),
                        "addedRevenue": net_profit,
                        "feeAddress": fee_address,
                    }
                    self.api_requester.cunarist(
                        "POST", "/api/solsol/automated-revenue", payload
                    )

        # ■■■■■ cancel conflicting orders ■■■■■

        self.cancel_conflicting_orders()

    def save_unrealized_changes(self, *args, **kwargs):
        with datalocks.hold("transactor_unrealized_changes"):
            sr = self.unrealized_changes.sort_index()
            sr = sr.astype(np.float32)
            unrealized_changes = sr.copy()
            self.unrealized_changes = sr
        unrealized_changes.to_pickle(self.workerpath + "/unrealized_changes.pickle")

    def open_exchange(self, *args, **kwargs):
        symbol = self.viewing_symbol
        webbrowser.open(f"https://www.binance.com/en/futures/{symbol}")

    def open_futures_wallet_page(self, *args, **kwargs):
        webbrowser.open("https://www.binance.com/en/my/wallet/account/futures")

    def open_api_management_page(self, *args, **kwargs):
        webbrowser.open("https://www.binance.com/en/my/settings/api-management")

    def update_keys(self, *args, **kwargs):
        server = kwargs.get("server", "real")

        def job():
            return (
                core.window.lineEdit_4.text(),
                core.window.lineEdit_6.text(),
            )

        returned = core.window.undertake(job, True)

        new_keys = {}
        new_keys["binance_api"] = returned[0]
        new_keys["binance_secret"] = returned[1]

        self.keys = new_keys

        filepath = self.workerpath + "/keys.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(new_keys, file, indent=4)

        new_keys = {}
        new_keys["server"] = server
        new_keys["binance_api"] = returned[0]
        new_keys["binance_secret"] = returned[1]

        self.api_requester.update_keys(new_keys)
        self.update_user_data_stream()

    def update_automation_settings(self, *args, **kwargs):
        # ■■■■■ get information about strategy ■■■■■

        strategy_index = core.window.undertake(
            lambda: core.window.comboBox_2.currentIndex(), True
        )
        self.automation_settings["strategy_index"] = strategy_index

        self.display_lines()

        # ■■■■■ is automation turned on ■■■■■

        is_checked = core.window.undertake(
            lambda: core.window.checkBox.isChecked(), True
        )

        if is_checked:
            current_moment = datetime.now(timezone.utc).replace(microsecond=0)
            current_moment = current_moment - timedelta(
                seconds=current_moment.second % 10
            )
            count_start_time = current_moment - timedelta(hours=24)
            with datalocks.hold("collector_candle_data"):
                df = collector.me.candle_data
                cumulated_moments = len(df[count_start_time:].dropna())
            needed_moments = 24 * 60 * 60 / 10
            ratio = cumulated_moments / needed_moments
            if ratio < 1:
                is_insufficient = True
            else:
                is_insufficient = False

            if is_insufficient:
                question = [
                    "Cumulation rate is not 100%",
                    "For auto transaction to work, the past 24"
                    " hour accumulation rate of candle data must be 100%. Even if"
                    " auto transaction is turned on, nothing happens until the"
                    " cumulation rate reaches 100%.",
                    ["Okay"],
                ]
                core.window.ask(question)

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

        range_start = core.window.undertake(
            lambda: core.window.plot_widget.getAxis("bottom").range[0], True
        )
        range_start = max(range_start, 0)
        range_start = datetime.fromtimestamp(range_start, tz=timezone.utc)

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        range_end = core.window.undertake(
            lambda: core.window.plot_widget.getAxis("bottom").range[1], True
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

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        with datalocks.hold("transactor_unrealized_changes"):
            unrealized_changes = self.unrealized_changes[range_start:range_end].copy()
        with datalocks.hold("transactor_asset_record"):
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

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        widget = core.window.plot_widget.getAxis("left")
        view_range = core.window.undertake(lambda w=widget: w.range, True)
        range_down = view_range[0]
        range_up = view_range[1]
        price_range_height = (1 - range_down / range_up) * 100

        text = ""
        text += f"Visible time range {range_days}d {range_hours}h {range_minutes}s"
        text += "  ⦁  "
        text += "Visible price range"
        text += f" {price_range_height:.2f}%"
        text += "  ⦁  "
        text += f"Transaction count {symbol_change_count}({total_change_count})"
        text += "  ⦁  "
        text += "Transaction amount"
        text += f" ×{symbol_margin_ratio:.4f}({total_margin_ratio:.4f})"
        text += "  ⦁  "
        text += f"Total realized profit {symbol_yield:+.4f}({total_yield:+.4f})%"
        text += "  ⦁  "
        text += "Lowest unrealized profit"
        text += f" {min_unrealized_change*100:+.4f}%"
        core.window.undertake(lambda t=text: core.window.label_8.setText(t), False)

    def set_minimum_view_range(self, *args, **kwargs):
        def job():
            widget = core.window.plot_widget
            range_down = widget.getAxis("left").range[0]
            widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)
            widget = core.window.plot_widget_1
            range_down = widget.getAxis("left").range[0]
            widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)

        core.window.undertake(job, False)

    def display_strategy_index(self, *args, **kwargs):
        strategy_index = self.automation_settings["strategy_index"]
        core.window.undertake(
            lambda i=strategy_index: core.window.comboBox_2.setCurrentIndex(i),
            False,
        )

    def display_lines(self, *args, **kwargs):
        # ■■■■■ start the task ■■■■■

        periodic = kwargs.get("periodic", False)
        frequent = kwargs.get("frequent", False)
        only_light_lines = kwargs.get("only_light_lines", False)

        if only_light_lines:
            task_name = "display_light_transaction_lines"
        else:
            task_name = "display_all_transaction_lines"

        task_id = stop_flag.make(task_name)

        # ■■■■■ check drawing mode ■■■■■

        should_draw_frequently = self.should_draw_frequently

        if frequent:
            if not should_draw_frequently:
                return

        # ■■■■■ check if the data exists ■■■■■

        with datalocks.hold("collector_candle_data"):
            if len(collector.me.candle_data) == 0:
                return

        # ■■■■■ wait for the latest data to be added ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        if periodic:
            for _ in range(50):
                if stop_flag.find(task_name, task_id):
                    return
                with datalocks.hold("collector_candle_data"):
                    last_index = collector.me.candle_data.index[-1]
                    if last_index == before_moment:
                        break
                time.sleep(0.1)

        # ■■■■■ get ready for task duration measurement ■■■■■

        task_start_time = datetime.now(timezone.utc)

        # ■■■■■ check things ■■■■■

        symbol = self.viewing_symbol
        strategy_index = self.automation_settings["strategy_index"]
        strategy = strategist.me.strategies[strategy_index]

        # ■■■■■ get light data ■■■■■

        with datalocks.hold("collector_realtime_data_chunks"):
            before_chunk = collector.me.realtime_data_chunks[-2].copy()
            current_chunk = collector.me.realtime_data_chunks[-1].copy()
        realtime_data = np.concatenate((before_chunk, current_chunk))
        with datalocks.hold("collector_aggregate_trades"):
            aggregate_trades = collector.me.aggregate_trades.copy()

        # ■■■■■ draw light lines ■■■■■

        # mark price
        data_x = realtime_data["index"].astype(np.int64) / 10**9
        data_y = realtime_data[str((symbol, "Mark Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = core.window.transaction_lines["mark_price"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # last price
        data_x = aggregate_trades["index"].astype(np.int64) / 10**9
        data_y = aggregate_trades[str((symbol, "Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = core.window.transaction_lines["last_price"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # last trade volume
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
        widget = core.window.transaction_lines["last_volume"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # book tickers
        data_x = realtime_data["index"].astype(np.int64) / 10**9
        data_y = realtime_data[str((symbol, "Best Bid Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = core.window.transaction_lines["book_tickers"][0]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        data_x = realtime_data["index"].astype(np.int64) / 10**9
        data_y = realtime_data[str((symbol, "Best Ask Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = core.window.transaction_lines["book_tickers"][1]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # open orders
        boundaries = [
            open_order["boundary"]
            for open_order in self.account_state["open_orders"][symbol].values()
            if "boundary" in open_order
        ]
        first_moment = self.account_state["observed_until"] - timedelta(hours=12)
        last_moment = self.account_state["observed_until"] + timedelta(hours=12)
        for turn, widget in enumerate(core.window.transaction_lines["boundaries"]):
            if turn < len(boundaries):
                boundary = boundaries[turn]
                data_x = np.linspace(
                    first_moment.timestamp(), last_moment.timestamp(), num=1000
                )
                data_y = np.linspace(boundary, boundary, num=1000)
                widget = core.window.transaction_lines["boundaries"][turn]

                def job(widget=widget, data_x=data_x, data_y=data_y):
                    widget.setData(data_x, data_y)

                if stop_flag.find(task_name, task_id):
                    return
                core.window.undertake(job, False)
            else:
                if stop_flag.find(task_name, task_id):
                    return
                core.window.undertake(lambda w=widget: w.clear(), False)

        # entry price
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
        widget = core.window.transaction_lines["entry_price"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # ■■■■■ record task duration ■■■■■

        if only_light_lines:
            duration = (datetime.now(timezone.utc) - task_start_time).total_seconds()
            remember_task_durations.add(task_name, duration)

        # ■■■■■ stop if the target is only light lines ■■■■■

        if only_light_lines:
            return

        # ■■■■■ set range of heavy data ■■■■■

        if should_draw_frequently:
            slice_from = datetime.now(timezone.utc) - timedelta(hours=24)
            slice_until = datetime.now(timezone.utc)
        else:
            current_year = datetime.now(timezone.utc).year
            slice_from = datetime(current_year, 1, 1, tzinfo=timezone.utc)
            slice_until = datetime.now(timezone.utc)
        slice_until -= timedelta(seconds=1)
        get_from = slice_from - timedelta(days=7)

        # ■■■■■ get heavy data ■■■■■

        with datalocks.hold("collector_candle_data"):
            candle_data = collector.me.candle_data
            candle_data = candle_data[get_from:slice_until][[symbol]]
            candle_data = candle_data.copy()
        with datalocks.hold("transactor_unrealized_changes"):
            unrealized_changes = self.unrealized_changes.copy()
        with datalocks.hold("transactor_asset_record"):
            asset_record = self.asset_record
            if len(asset_record) > 0:
                last_asset = asset_record.iloc[-1]["Result Asset"]
            else:
                last_asset = None
            before_record = asset_record[:slice_from]
            asset_record = asset_record[slice_from:]
            if len(before_record) > 0:
                before_asset = before_record.iloc[-1]["Result Asset"]
            else:
                before_asset = None
            asset_record = asset_record.copy()

        candle_data = candle_data[slice_from:]

        # ■■■■■ maniuplate heavy data ■■■■■

        # add the right end

        if len(candle_data) > 0:
            last_written_moment = candle_data.index[-1]
            new_moment = last_written_moment + timedelta(seconds=10)
            new_index = candle_data.index.union([new_moment])
            candle_data = candle_data.reindex(new_index)

        if last_asset is not None:
            observed_until = self.account_state["observed_until"]
            if len(asset_record) == 0 or asset_record.index[-1] < observed_until:
                asset_record.loc[observed_until, "Cause"] = "other"
                asset_record.loc[observed_until, "Result Asset"] = last_asset
                asset_record = asset_record.sort_index()

        # add the left end

        if before_asset is not None:
            asset_record.loc[slice_from, "Cause"] = "other"
            asset_record.loc[slice_from, "Result Asset"] = before_asset
            asset_record = asset_record.sort_index()

        # ■■■■■ draw heavy lines ■■■■■

        # price movement
        index_ar = candle_data.index.to_numpy(dtype=np.int64) / 10**9
        open_ar = candle_data[(symbol, "Open")].to_numpy()
        close_ar = candle_data[(symbol, "Close")].to_numpy()
        high_ar = candle_data[(symbol, "High")].to_numpy()
        low_ar = candle_data[(symbol, "Low")].to_numpy()
        rise_ar = close_ar > open_ar
        fall_ar = close_ar < open_ar
        stay_ar = close_ar == open_ar
        length = len(index_ar)
        nan_ar = np.empty(length)
        nan_ar[:] = np.nan

        data_x = np.stack(
            [
                index_ar[rise_ar] + 2,
                index_ar[rise_ar] + 5,
                index_ar[rise_ar],
                index_ar[rise_ar] + 5,
                index_ar[rise_ar] + 8,
                index_ar[rise_ar],
                index_ar[rise_ar] + 5,
                index_ar[rise_ar] + 5,
                index_ar[rise_ar],
            ],
            axis=1,
        ).reshape(-1)
        data_y = np.stack(
            [
                open_ar[rise_ar],
                open_ar[rise_ar],
                nan_ar[rise_ar],
                close_ar[rise_ar],
                close_ar[rise_ar],
                nan_ar[rise_ar],
                high_ar[rise_ar],
                low_ar[rise_ar],
                nan_ar[rise_ar],
            ],
            axis=1,
        ).reshape(-1)
        widget = core.window.transaction_lines["price_rise"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        data_x = np.stack(
            [
                index_ar[fall_ar] + 2,
                index_ar[fall_ar] + 5,
                index_ar[fall_ar],
                index_ar[fall_ar] + 5,
                index_ar[fall_ar] + 8,
                index_ar[fall_ar],
                index_ar[fall_ar] + 5,
                index_ar[fall_ar] + 5,
                index_ar[fall_ar],
            ],
            axis=1,
        ).reshape(-1)
        data_y = np.stack(
            [
                open_ar[fall_ar],
                open_ar[fall_ar],
                nan_ar[fall_ar],
                close_ar[fall_ar],
                close_ar[fall_ar],
                nan_ar[fall_ar],
                high_ar[fall_ar],
                low_ar[fall_ar],
                nan_ar[fall_ar],
            ],
            axis=1,
        ).reshape(-1)
        widget = core.window.transaction_lines["price_fall"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        data_x = np.stack(
            [
                index_ar[stay_ar] + 2,
                index_ar[stay_ar] + 5,
                index_ar[stay_ar],
                index_ar[stay_ar] + 5,
                index_ar[stay_ar] + 8,
                index_ar[stay_ar],
                index_ar[stay_ar] + 5,
                index_ar[stay_ar] + 5,
                index_ar[stay_ar],
            ],
            axis=1,
        ).reshape(-1)
        data_y = np.stack(
            [
                open_ar[stay_ar],
                open_ar[stay_ar],
                nan_ar[stay_ar],
                close_ar[stay_ar],
                close_ar[stay_ar],
                nan_ar[stay_ar],
                high_ar[stay_ar],
                low_ar[stay_ar],
                nan_ar[stay_ar],
            ],
            axis=1,
        ).reshape(-1)
        widget = core.window.transaction_lines["price_stay"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # wobbles
        sr = candle_data[(symbol, "High")]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["wobbles"][0]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        sr = candle_data[(symbol, "Low")]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["wobbles"][1]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # trade volume
        sr = candle_data[(symbol, "Volume")]
        sr = sr.fillna(value=0)
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["volume"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # asset
        data_x = asset_record["Result Asset"].index.to_numpy(dtype=np.int64) / 10**9
        data_y = asset_record["Result Asset"].to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["asset"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # asset with unrealized profit
        sr = asset_record["Result Asset"]
        if len(sr) >= 2:
            sr = sr.resample("10S").ffill()
        unrealized_changes_sr = unrealized_changes.reindex(sr.index)
        sr = sr * (1 + unrealized_changes_sr)
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9 + 5
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["asset_with_unrealized_profit"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # buy and sell
        df = asset_record.loc[asset_record["Symbol"] == symbol]
        df = df[df["Side"] == "sell"]
        sr = df["Fill Price"]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["sell"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        df = asset_record.loc[asset_record["Symbol"] == symbol]
        df = df[df["Side"] == "buy"]
        sr = df["Fill Price"]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["buy"]

        def job(widget=widget, data_x=data_x, data_y=data_y):
            widget.setData(data_x, data_y)

        if stop_flag.find(task_name, task_id):
            return
        core.window.undertake(job, False)

        # ■■■■■ record task duration ■■■■■

        duration = (datetime.now(timezone.utc) - task_start_time).total_seconds()
        remember_task_durations.add(task_name, duration)

        # ■■■■■ make indicators ■■■■■

        indicators_script = strategy["indicators_script"]
        compiled_indicators_script = compile(indicators_script, "<string>", "exec")
        target_symbols = user_settings.get_data_settings()["target_symbols"]

        indicators = process_toss.apply(
            make_indicators.do,
            target_symbols=target_symbols,
            candle_data=candle_data,
            compiled_indicators_script=compiled_indicators_script,
        )

        indicators = indicators[slice_from:]

        # ■■■■■ delete indicator data if strategy wants ■■■■■

        if strategy["hide_indicators"]:
            indicators = indicators.iloc[0:0]

        # ■■■■■ draw strategy lines ■■■■■

        # price indicators
        df = indicators[symbol]["Price"]
        data_x = df.index.to_numpy(dtype=np.int64) / 10**9
        data_x += 5
        line_list = core.window.transaction_lines["price_indicators"]
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

                if stop_flag.find(task_name, task_id):
                    return
                core.window.undertake(job, False)
            else:
                if stop_flag.find(task_name, task_id):
                    return
                core.window.undertake(lambda w=widget: w.clear(), False)

        # trade volume indicators
        df = indicators[symbol]["Volume"]
        data_x = df.index.to_numpy(dtype=np.int64) / 10**9
        data_x += 5
        line_list = core.window.transaction_lines["volume_indicators"]
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

                if stop_flag.find(task_name, task_id):
                    return
                core.window.undertake(job, False)
            else:
                if stop_flag.find(task_name, task_id):
                    return
                core.window.undertake(lambda w=widget: w.clear(), False)

        # abstract indicators
        df = indicators[symbol]["Abstract"]
        data_x = df.index.to_numpy(dtype=np.int64) / 10**9
        data_x += 5
        line_list = core.window.transaction_lines["abstract_indicators"]
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

                if stop_flag.find(task_name, task_id):
                    return
                core.window.undertake(job, False)
            else:
                if stop_flag.find(task_name, task_id):
                    return
                core.window.undertake(lambda w=widget: w.clear(), False)

    def toggle_frequent_draw(self, *args, **kwargs):
        is_checked = args[0]
        if is_checked:
            self.should_draw_frequently = True
        else:
            self.should_draw_frequently = False
        self.display_lines()

    def update_viewing_symbol(self, *args, **kwargs):
        def job():
            return core.window.comboBox_4.currentText()

        alias = core.window.undertake(job, True)
        symbol = core.window.alias_to_symbol[alias]
        self.viewing_symbol = symbol

        self.display_lines()
        self.display_asset_information()
        self.display_range_information()

    def display_asset_information(self, *args, **kwargs):
        # ■■■■■ is it the recent information? ■■■■■

        time_passed = datetime.now(timezone.utc) - self.account_state["observed_until"]
        if time_passed > timedelta(seconds=30):
            text = (
                "Couldn't get the latest info on your Binance account due to a problem"
                " with your key or connection to the Binance server."
            )
            core.window.undertake(lambda t=text: core.window.label_16.setText(t), False)
            return

        # ■■■■■ display the information ■■■■■

        position = self.account_state["positions"][self.viewing_symbol]
        if position["direction"] == "long":
            direction_text = "long"
        elif position["direction"] == "short":
            direction_text = "short"
        else:
            direction_text = "none"
        margin_sum = 0
        for each_position in self.account_state["positions"].values():
            margin_sum += each_position["margin"]

        with datalocks.hold("transactor_auto_order_record"):
            if len(self.auto_order_record) > 0:
                total_profit = self.auto_order_record["Net Profit"].sum()
            else:
                total_profit = 0

        text = ""
        text += "Total asset"
        text += f" ＄{self.account_state['wallet_balance']:.4f}"
        text += "  ⦁  "
        text += f"Investment ＄{position['margin']:.4f}"
        text += f"({margin_sum:.4f})"
        text += "  ⦁  "
        text += f"Direction {direction_text}"
        text += "  ⦁  "
        text += "Entry price"
        text += f" ＄{position['entry_price']:.4f}"
        text += "  ⦁  "
        text += f"Automated revenue ＄{total_profit:+.4f}"

        core.window.undertake(lambda t=text: core.window.label_16.setText(t), False)

    def perform_transaction(self, *args, **kwargs):
        # ■■■■■ stop if internet connection is not present ■■■■

        if not check_internet.connected():
            return

        # ■■■■■ stop if the automation is turned off ■■■■■

        if not self.automation_settings["should_transact"]:
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
                    before_value = core.window.undertake(
                        lambda: core.window.progressBar_2.value(), True
                    )
                    remaining = 1000 - before_value
                    new_value = before_value + math.ceil(remaining * 0.2)

                def job(new_value=new_value):
                    core.window.progressBar_2.setValue(new_value)

                core.window.undertake(job, False)
                time.sleep(0.01)

            core.window.undertake(lambda: core.window.progressBar_2.setValue(0), False)

        thread_toss.apply_async(job)

        # ■■■■■ moment ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        # ■■■■■ check if the data exists ■■■■■

        with datalocks.hold("collector_candle_data"):
            if len(collector.me.candle_data) == 0:
                # case when the app is executed for the first time
                return

        # ■■■■■ wait for the latest data to be added ■■■■■

        for _ in range(50):
            with datalocks.hold("collector_candle_data"):
                last_index = collector.me.candle_data.index[-1]
                if last_index == before_moment:
                    break
            time.sleep(0.1)

        # ■■■■■ stop if the accumulation rate is not 100% ■■■■■

        count_start_time = current_moment - timedelta(hours=24)

        with datalocks.hold("collector_candle_data"):
            df = collector.me.candle_data
            cumulated_moments = len(df[count_start_time:].dropna())
        needed_moments = 24 * 60 * 60 / 10
        ratio = cumulated_moments / needed_moments
        if ratio < 1:
            is_cycle_done = True
            return

        # ■■■■■ get the candle data ■■■■■

        slice_from = datetime.now(timezone.utc) - timedelta(days=7)
        with datalocks.hold("collector_candle_data"):
            df = collector.me.candle_data
            partial_candle_data = df[slice_from:].copy()

        # ■■■■■ make decision ■■■■■

        target_symbols = user_settings.get_data_settings()["target_symbols"]

        strategy_index = self.automation_settings["strategy_index"]
        strategy = strategist.me.strategies[strategy_index]

        indicators_script = strategy["indicators_script"]
        compiled_indicators_script = compile(indicators_script, "<string>", "exec")

        indicators = process_toss.apply(
            make_indicators.do,
            target_symbols=target_symbols,
            candle_data=partial_candle_data,
            compiled_indicators_script=compiled_indicators_script,
        )

        current_candle_data = partial_candle_data.to_records()[-1]
        current_indicators = indicators.to_records()[-1]
        decision_script = strategy["decision_script"]
        compiled_decision_script = compile(decision_script, "<string>", "exec")

        decision, scribbles = process_toss.apply(
            decide.choose,
            target_symbols=target_symbols,
            current_moment=current_moment,
            current_candle_data=current_candle_data,
            current_indicators=current_indicators,
            account_state=copy.deepcopy(self.account_state),
            scribbles=self.scribbles,
            compiled_decision_script=compiled_decision_script,
        )
        self.scribbles = scribbles

        # ■■■■■ record task duration ■■■■■

        is_cycle_done = True
        duration = (datetime.now(timezone.utc) - current_moment).total_seconds()
        remember_task_durations.add("perform_transaction", duration)

        # ■■■■■ place order ■■■■■

        self.place_order(decision)

    def display_day_range(self, *args, **kwargs):
        range_start = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
        range_end = datetime.now(timezone.utc).timestamp()
        widget = core.window.plot_widget

        def job(range_start=range_start, range_end=range_end):
            widget.setXRange(range_start, range_end)

        core.window.undertake(job, False)

    def open_testnet_exchange(self, *args, **kwargs):
        symbol = self.viewing_symbol
        webbrowser.open(f"https://testnet.binancefuture.com/en/futures/{symbol}")

    def match_graph_range(self, *args, **kwargs):
        range_start = core.window.undertake(
            lambda: core.window.plot_widget_2.getAxis("bottom").range[0], True
        )
        range_end = core.window.undertake(
            lambda: core.window.plot_widget_2.getAxis("bottom").range[1], True
        )
        widget = core.window.plot_widget

        def job(range_start=range_start, range_end=range_end):
            widget.setXRange(range_start, range_end, padding=0)

        core.window.undertake(job, False)

    def update_mode_settings(self, *args, **kwargs):
        widget = core.window.spinBox
        desired_leverage = core.window.undertake(lambda w=widget: w.value(), True)
        self.mode_settings["desired_leverage"] = desired_leverage

        # ■■■■■ tell if some symbol's leverage cannot be set as desired ■■■■■

        target_symbols = user_settings.get_data_settings()["target_symbols"]
        target_max_leverages = {}
        for symbol in target_symbols:
            max_leverage = self.secret_memory["maximum_leverages"].get(symbol, 125)
            target_max_leverages[symbol] = max_leverage
        lowest_max_leverage = min(target_max_leverages.values())

        if lowest_max_leverage < desired_leverage:
            question = [
                "Leverage on some symbols cannot be set as desired",
                "Binance has its own leverage limit per market. For some symbols,"
                " leverage will be set as high as it can be, but not as same as the"
                " value entered. Generally, situation gets safer in terms of lowest"
                " unrealized changes and profit turns out to be a bit lower than"
                " simulation prediction with the same leverage.",
                ["Show details", "Okay"],
            ]
            answer = core.window.ask(question)
            if answer == 1:
                texts = []
                for symbol, max_leverage in target_max_leverages.items():
                    texts.append(f"{symbol} {max_leverage}")
                text = "\n".join(texts)
                question = [
                    "These are highest available leverages",
                    text,
                    ["Okay"],
                ]
                core.window.ask(question)

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

        for about_symbol in about_exchange["symbols"]:
            symbol = about_symbol["symbol"]

            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "MIN_NOTIONAL":
                    break
            minimum_notional = float(about_filter["notional"])
            self.secret_memory["minimum_notionals"][symbol] = minimum_notional

            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "LOT_SIZE":
                    break
            maximum_quantity = float(about_filter["maxQty"])
            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "MARKET_LOT_SIZE":
                    break
            maximum_quantity = min(maximum_quantity, float(about_filter["maxQty"]))
            self.secret_memory["maximum_quantities"][symbol] = maximum_quantity

            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "PRICE_FILTER":
                    break
            ticksize = float(about_filter["tickSize"])
            price_precision = int(math.log10(1 / ticksize))
            self.secret_memory["price_precisions"][symbol] = price_precision

            for about_filter in about_symbol["filters"]:
                if about_filter["filterType"] == "LOT_SIZE":
                    break
            stepsize = float(about_filter["stepSize"])
            quantity_precision = int(math.log10(1 / stepsize))
            self.secret_memory["quantity_precisions"][symbol] = quantity_precision

        # ■■■■■ request leverage bracket information ■■■■■

        try:
            payload = {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
            response = self.api_requester.binance(
                http_method="GET",
                path="/fapi/v1/leverageBracket",
                payload=payload,
            )
            about_brackets = response

            for about_bracket in about_brackets:
                symbol = about_bracket["symbol"]
                max_leverage = about_bracket["brackets"][0]["initialLeverage"]
                self.secret_memory["maximum_leverages"][symbol] = max_leverage
        except ApiRequestError:
            # when the key is not ready
            return

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

        thread_toss.map(job, user_settings.get_data_settings()["target_symbols"])

        # ■■■■■ update account state ■■■■■

        # observed until
        self.account_state["observed_until"] = current_moment

        # wallet_balance
        for about_asset in about_account["assets"]:
            if about_asset["asset"] == user_settings.get_data_settings()["asset_token"]:
                break
        wallet_balance = float(about_asset["walletBalance"])
        self.account_state["wallet_balance"] = wallet_balance

        # positions
        for symbol in user_settings.get_data_settings()["target_symbols"]:
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
        for symbol in user_settings.get_data_settings()["target_symbols"]:
            open_orders[symbol] = {}

        for symbol in user_settings.get_data_settings()["target_symbols"]:
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

        for symbol in user_settings.get_data_settings()["target_symbols"]:
            for about_position in about_account["positions"]:
                if about_position["symbol"] == symbol:
                    break
            leverage = int(about_position["leverage"])
            self.secret_memory["leverages"][symbol] = leverage

        # ■■■■■ record unrealized change ■■■■■

        for about_asset in about_account["assets"]:
            if about_asset["asset"] == user_settings.get_data_settings()["asset_token"]:
                break
        # unrealized profit is not included in walletBalance
        wallet_balance = float(about_asset["walletBalance"])
        if wallet_balance != 0:
            unrealized_profit = float(about_asset["unrealizedProfit"])
            unrealized_change = unrealized_profit / wallet_balance
        else:
            unrealized_change = 0

        with datalocks.hold("transactor_unrealized_changes"):
            self.unrealized_changes[before_moment] = unrealized_change

        # ■■■■■ make an asset trace if it's blank ■■■■■

        with datalocks.hold("transactor_asset_record"):
            if len(self.asset_record) == 0:
                for about_asset in about_account["assets"]:
                    if (
                        about_asset["asset"]
                        == user_settings.get_data_settings()["asset_token"]
                    ):
                        break
                wallet_balance = float(about_asset["walletBalance"])
                current_time = datetime.now(timezone.utc)
                self.asset_record.loc[current_time, "Cause"] = "other"
                self.asset_record.loc[current_time, "Result Asset"] = wallet_balance
                self.asset_record.to_pickle(self.workerpath + "/asset_record.pickle")

        # ■■■■■ when the wallet balance changed for no good reason ■■■■■

        for about_asset in about_account["assets"]:
            if about_asset["asset"] == user_settings.get_data_settings()["asset_token"]:
                break
        wallet_balance = float(about_asset["walletBalance"])

        with datalocks.hold("transactor_asset_record"):
            last_index = self.asset_record.index[-1]
            last_asset = self.asset_record.loc[last_index, "Result Asset"]

        if wallet_balance == 0:
            pass
        elif abs(wallet_balance - last_asset) / wallet_balance > 10**-9:
            # when the difference is bigger than one billionth
            # referal fee, funding fee, wallet transfer, etc..
            with datalocks.hold("transactor_asset_record"):
                current_time = datetime.now(timezone.utc)
                self.asset_record.loc[current_time, "Cause"] = "other"
                self.asset_record.loc[current_time, "Result Asset"] = wallet_balance
                self.asset_record.to_pickle(self.workerpath + "/asset_record.pickle")
                self.asset_record = self.asset_record.sort_index()
        else:
            # when the difference is small enough to consider as an numeric error
            with datalocks.hold("transactor_asset_record"):
                last_index = self.asset_record.index[-1]
                self.asset_record.loc[last_index, "Result Asset"] = wallet_balance

        # ■■■■■ correct mode of the account market if automation is turned on ■■■■■

        if self.automation_settings["should_transact"]:

            def job(symbol):
                for about_position in about_account["positions"]:
                    if about_position["symbol"] == symbol:
                        break
                current_leverage = int(about_position["leverage"])

                desired_leverage = self.mode_settings["desired_leverage"]
                maximum_leverages = self.secret_memory["maximum_leverages"]
                max_leverage = maximum_leverages.get(symbol, 125)
                goal_leverage = min(desired_leverage, max_leverage)

                if current_leverage != goal_leverage:
                    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                    payload = {
                        "symbol": symbol,
                        "timestamp": timestamp,
                        "leverage": goal_leverage,
                    }
                    self.api_requester.binance(
                        http_method="POST",
                        path="/fapi/v1/leverage",
                        payload=payload,
                    )

            thread_toss.map(job, user_settings.get_data_settings()["target_symbols"])

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

            thread_toss.map(job, user_settings.get_data_settings()["target_symbols"])

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

        for symbol in user_settings.get_data_settings()["target_symbols"]:
            if symbol not in decision.keys():
                continue

            with datalocks.hold("collector_aggregate_trades"):
                ar = collector.me.aggregate_trades[-10000:].copy()
            temp_ar = ar[str((symbol, "Price"))]
            temp_ar = temp_ar[temp_ar != 0]
            current_price = float(temp_ar[-1])

            leverage = self.secret_memory["leverages"][symbol]
            maximum_quantity = self.secret_memory["maximum_quantities"][symbol]
            minimum_notional = self.secret_memory["minimum_notionals"][symbol]
            price_precision = self.secret_memory["price_precisions"][symbol]
            quantity_precision = self.secret_memory["quantity_precisions"][symbol]

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
                response = self.api_requester.binance(
                    http_method="POST",
                    path="/fapi/v1/order",
                    payload=payload,
                )
                order_symbol = response["symbol"]
                order_id = response["orderId"]
                timestamp = response["updateTime"] / 1000
                update_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                with datalocks.hold("transactor_auto_order_record"):
                    self.auto_order_record.loc[update_time, "Symbol"] = order_symbol
                    self.auto_order_record.loc[update_time, "Order ID"] = order_id
                    self.auto_order_record.loc[update_time, "Net Profit"] = 0
                    self.auto_order_record = self.auto_order_record.sort_index()

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
        for symbol in user_settings.get_data_settings()["target_symbols"]:
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

    def move_view_range(self, *args, **kwargs):
        if not self.should_draw_frequently:
            return

        widget = core.window.plot_widget
        axis = widget.getAxis("bottom")

        before_range = core.window.undertake(lambda: axis.range, True)
        range_start = before_range[0]
        range_end = before_range[1]

        if range_end - range_start < 6 * 60 * 60:  # six hours
            return

        def job():
            widget.setXRange(range_start + 10, range_end + 10, padding=0)

        core.window.undertake(job, False)

    def pay_fees(self, *args, **kwargs):
        asset_token = user_settings.get_data_settings()["asset_token"]
        solsol_address = "0xF9A7E35254cc8A9A9C811849CAF672F10fAB7366"

        payload = {
            "solsolPasscode": "SBJyXScaIEIteBPcqpMTMAG3T6B75rb4",
            "deviceIdentifier": getmac.get_mac_address(),
        }
        response = self.api_requester.cunarist(
            "GET", "/api/solsol/automated-revenue", payload
        )
        should_pay_now = response["shouldPayNow"]
        solsol_left_fee = response["solsolLeftFee"]
        strategy_left_fee = response["strategyLeftFee"]

        if not should_pay_now:
            return

        payload = {
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        response = self.api_requester.binance("GET", "/api/v3/account", payload)
        spot_balances = response["balances"]
        dollars_prepared = 0
        for spot_balance in spot_balances:
            if spot_balance["asset"] == "BUSD":
                dollars_prepared = spot_balance["free"]
                break

        dollars_needed = 0

        if solsol_left_fee > 10:
            dollars_needed += solsol_left_fee + 10
            # more for binance withdrawl fee
        for fee in strategy_left_fee.values():
            if fee > 10:
                dollars_needed += fee + 10

        dollars_transfer = dollars_needed - dollars_prepared
        if dollars_transfer > 0:
            payload = {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "type": "UMFUTURE_MAIN",
                "amount": ball.ceil(dollars_transfer, 4),
                "asset": asset_token,
            }
            self.api_requester.binance("POST", "/sapi/v1/asset/transfer", payload)

        if asset_token == "USDT":
            payload = {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "symbol": "BUSDUSDT",
                "side": "BUY",
                "type": "MARKET",
                "quantity": ball.ceil(dollars_transfer, 4),
            }
            self.api_requester.binance("POST", "/api/v3/order", payload)

        new_orders = []
        new_orders.append(
            {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "coin": "BUSD",
                "network": "BSC",
                "address": solsol_address,
                "amount": ball.ceil(solsol_left_fee, 4),
            }
        )
        for address, fee in strategy_left_fee.items():
            new_orders.append(
                {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "coin": "BUSD",
                    "network": "BSC",
                    "address": address,
                    "amount": ball.ceil(fee, 4),
                }
            )

        strategy_fee_paid = {}

        def job(payload):
            self.api_requester.binance(
                http_method="POST",
                path="/sapi/v1/capital/withdraw/apply",
                payload=payload,
            )
            address = payload["address"]
            this_fee_paid = payload["amount"]
            strategy_fee_paid[address] = this_fee_paid

        thread_toss.map(job, new_orders)

        logging.getLogger("solsol").info(
            "Fee payment completed.\n" + json.dumps(strategy_fee_paid, indent=4)
        )

        solsol_fee_paid = 0
        if solsol_address in strategy_fee_paid.keys():
            solsol_fee_paid = strategy_fee_paid.pop(solsol_address)

        payload = {
            "solsolPasscode": "SBJyXScaIEIteBPcqpMTMAG3T6B75rb4",
            "deviceIdentifier": getmac.get_mac_address(),
            "solsolFeePaid": solsol_fee_paid,
            "strategyFeePaid": strategy_fee_paid,
        }
        response = self.api_requester.cunarist(
            "PUT", "/api/solsol/automated-revenue", payload
        )


me = None


def bring_to_life():
    global me
    me = Transactor()
