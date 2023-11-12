import asyncio
import copy
import functools
import json
import logging
import math
import os
import pickle
import re
import webbrowser
from datetime import datetime, timedelta, timezone

import aiofiles
import numpy as np
import pandas as pd

from module import core
from module.instrument.api_request_error import ApiRequestError
from module.instrument.api_requester import ApiRequester
from module.instrument.api_streamer import ApiStreamer
from module.recipe import (
    ball,
    check_internet,
    datalocks,
    decide,
    make_indicators,
    remember_task_durations,
    standardize,
    stop_flag,
    user_settings,
)
from module.shelf.long_text_view import LongTextView
from module.worker import collector, strategist


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
            "is_key_restrictions_satisfied": True,
        }

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.viewing_symbol = user_settings.get_data_settings()["target_symbols"][0]
        self.should_draw_frequently = True

        self.account_state = standardize.account_state()

        self.scribbles = {}
        self.automation_settings = {
            "strategy_index": 0,
            "should_transact": False,
        }
        self.mode_settings = {
            "desired_leverage": 1,
        }
        self.keys = {
            "binance_api": "",
            "binance_secret": "",
        }
        self.unrealized_changes = standardize.unrealized_changes()
        self.asset_record = standardize.asset_record()
        self.auto_order_record = pd.DataFrame(
            columns=[
                "Symbol",
                "Order ID",
            ],
            index=pd.DatetimeIndex([], tz="UTC"),
        )

        # ■■■■■ repetitive schedules ■■■■■

        core.window.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            second="*",
            kwargs={"only_light_lines": True, "frequent": True},
        )
        core.window.scheduler.add_job(
            self.display_status_information,
            trigger="cron",
            second="*",
        )
        core.window.scheduler.add_job(
            self.display_range_information,
            trigger="cron",
            second="*",
        )
        core.window.scheduler.add_job(
            self.cancel_conflicting_orders,
            trigger="cron",
            second="*",
        )
        core.window.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            second="*/10",
            kwargs={"periodic": True, "frequent": True},
        )
        core.window.scheduler.add_job(
            self.pan_view_range,
            trigger="cron",
            second="*/10",
        )
        core.window.scheduler.add_job(
            self.perform_transaction,
            trigger="cron",
            second="*/10",
        )
        core.window.scheduler.add_job(
            self.save_scribbles,
            trigger="cron",
            second="*/10",
        )
        core.window.scheduler.add_job(
            self.watch_binance,
            trigger="cron",
            second="*/10",
        )
        core.window.scheduler.add_job(
            self.organize_data,
            trigger="cron",
            minute="*",
        )
        core.window.scheduler.add_job(
            self.update_user_data_stream,
            trigger="cron",
            minute="*/10",
        )
        core.window.scheduler.add_job(
            self.save_large_data,
            trigger="cron",
            hour="*",
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamer = ApiStreamer(
            "",
            self.listen_to_account,
        )
        self.api_streamers = []

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functions = [
            lambda: self.update_user_data_stream(),
            lambda: self.watch_binance(),
        ]
        check_internet.add_connected_functions(connected_functions)

        disconnected_functions = []
        check_internet.add_disconnected_functions(disconnected_functions)

    async def load(self, *args, **kwargs):
        # scribbles
        try:
            filepath = self.workerpath + "/scribbles.pickle"
            async with aiofiles.open(filepath, "rb") as file:
                content = await file.read()
                self.scribbles = pickle.loads(content)
        except FileNotFoundError:
            pass
        await asyncio.sleep(0)

        # automation settings
        try:
            filepath = self.workerpath + "/automation_settings.json"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                content = await file.read()
                read_data = json.loads(content)
            self.automation_settings = read_data
            state = read_data["should_transact"]
            core.window.checkBox.setChecked(state)
            strategy_index = read_data["strategy_index"]
            core.window.comboBox_2.setCurrentIndex(strategy_index)
        except FileNotFoundError:
            pass
        await asyncio.sleep(0)

        # mode settings
        try:
            filepath = self.workerpath + "/mode_settings.json"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                content = await file.read()
                read_data = json.loads(content)
            self.mode_settings = read_data
            new_value = read_data["desired_leverage"]
            core.window.spinBox.setValue(new_value)
        except FileNotFoundError:
            pass
        await asyncio.sleep(0)

        # keys
        try:
            filepath = self.workerpath + "/keys.json"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                content = await file.read()
                keys = json.loads(content)
            text = keys["binance_api"]
            core.window.lineEdit_4.setText(text)
            text = keys["binance_secret"]
            core.window.lineEdit_6.setText(text)
            self.keys = keys
            self.api_requester.update_keys(keys)
        except FileNotFoundError:
            pass
        await asyncio.sleep(0)

        # unrealized changes
        try:
            filepath = self.workerpath + "/unrealized_changes.pickle"
            self.unrealized_changes = pd.read_pickle(filepath)
        except FileNotFoundError:
            pass
        await asyncio.sleep(0)

        # asset record
        try:
            filepath = self.workerpath + "/asset_record.pickle"
            self.asset_record = pd.read_pickle(filepath)
        except FileNotFoundError:
            pass
        await asyncio.sleep(0)

        # auto order record
        try:
            filepath = self.workerpath + "/auto_order_record.pickle"
            self.auto_order_record = pd.read_pickle(filepath)
        except FileNotFoundError:
            pass
        await asyncio.sleep(0)

    async def organize_data(self, *args, **kwargs):
        async with datalocks.hold("transactor_unrealized_changes"):
            sr = self.unrealized_changes
            original_index = sr.index
            unique_index = original_index.drop_duplicates()
            sr = sr.reindex(unique_index)
            sr = sr.sort_index()
            sr = sr.astype(np.float32)
            self.unrealized_changes = sr

        async with datalocks.hold("transactor_auto_order_record"):
            df = self.auto_order_record
            original_index = df.index
            unique_index = original_index.drop_duplicates()
            df = df.reindex(unique_index)
            df = df.sort_index()
            df = df.iloc[-(2**16) :].copy()
            self.auto_order_record = df

        async with datalocks.hold("transactor_asset_record"):
            df = self.asset_record
            original_index = df.index
            unique_index = original_index.drop_duplicates()
            df = df.reindex(unique_index)
            df = df.sort_index()
            self.asset_record = df

    async def save_large_data(self, *args, **kwargs):
        async with datalocks.hold("transactor_unrealized_changes"):
            unrealized_changes = self.unrealized_changes.copy()
        unrealized_changes.to_pickle(self.workerpath + "/unrealized_changes.pickle")

        async with datalocks.hold("transactor_auto_order_record"):
            auto_order_record = self.auto_order_record.copy()
        auto_order_record.to_pickle(self.workerpath + "/auto_order_record.pickle")

        async with datalocks.hold("transactor_asset_record"):
            asset_record = self.asset_record.copy()
        asset_record.to_pickle(self.workerpath + "/asset_record.pickle")

    async def save_scribbles(self, *args, **kwargs):
        filepath = self.workerpath + "/scribbles.pickle"
        async with aiofiles.open(filepath, "wb") as file:
            content = pickle.dumps(self.scribbles)
            await file.write(content)

    async def update_user_data_stream(self, *args, **kwargs):
        if not check_internet.connected():
            return

        try:
            payload = {}
            response = await self.api_requester.binance(
                http_method="POST",
                path="/fapi/v1/listenKey",
                payload=payload,
            )
        except ApiRequestError:
            return

        listen_key = response["listenKey"]

        self.api_streamer = ApiStreamer(
            "wss://fstream.binance.com/ws/" + listen_key,
            self.listen_to_account,
        )

    async def listen_to_account(self, *args, **kwargs):
        received = kwargs["received"]

        # ■■■■■ default values ■■■■■

        event_type = received["e"]
        event_timestamp = received["E"] / 1000
        event_time = datetime.fromtimestamp(event_timestamp, tz=timezone.utc)

        self.account_state["observed_until"] = event_time

        # ■■■■■ do the task according to event type ■■■■■

        if event_type == "listenKeyExpired":
            text = "Binance user data stream listen key got expired"
            logger = logging.getLogger("solie")
            logger.warning(text)
            await self.update_user_data_stream()

        if event_type == "ACCOUNT_UPDATE":
            about_update = received["a"]
            about_assets = about_update["B"]
            about_positions = about_update["P"]

            asset_token = user_settings.get_data_settings()["asset_token"]

            about_asset = {}
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

                about_position = {}
                target_symbols = user_settings.get_data_settings()["target_symbols"]
                if about_position["s"] not in target_symbols:
                    return

                symbol = about_position["s"]
                amount = float(about_position["pa"])
                entry_price = float(about_position["ep"])

                leverage = self.secret_memory["leverages"][symbol]
                margin = abs(amount) * entry_price / leverage
                if amount < 0:
                    direction = "short"
                elif amount > 0:
                    direction = "long"
                else:
                    direction = "none"

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
                        else:
                            raise ValueError("Cannot order with this side")
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
                    else:
                        raise ValueError("Cannot order with this side")
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
                        else:
                            raise ValueError("Cannot order with this side")
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
                    else:
                        raise ValueError("Cannot order with this side")
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
                        raise ValueError("Cannot order with this side")
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
                added_revenue = realized_profit - commission
                added_notional = last_filled_price * last_filled_quantity
                added_margin = added_notional / leverage
                added_margin_ratio = added_margin / wallet_balance

                async with datalocks.hold("transactor_auto_order_record"):
                    df = self.auto_order_record
                    symbol_df = df[df["Symbol"] == symbol]
                    unique_order_ids = symbol_df["Order ID"].unique()
                    if order_id in unique_order_ids:
                        mask_sr = symbol_df["Order ID"] == order_id

                async with datalocks.hold("transactor_asset_record"):
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
                        last_asset: float = self.asset_record.loc[
                            last_index, "Result Asset"
                        ]  # type:ignore
                        new_value = last_asset + added_revenue
                        self.asset_record.loc[last_index, "Result Asset"] = new_value
                    else:
                        record_time = event_time
                        while record_time in self.asset_record.index:
                            record_time += timedelta(milliseconds=1)
                        new_value = symbol
                        self.asset_record.loc[record_time, "Symbol"] = new_value
                        new_value = "sell" if side == "SELL" else "buy"
                        self.asset_record.loc[record_time, "Side"] = new_value
                        new_value = last_filled_price
                        self.asset_record.loc[record_time, "Fill Price"] = new_value
                        new_value = "maker" if is_maker else "taker"
                        self.asset_record.loc[record_time, "Role"] = new_value
                        new_value = added_margin_ratio
                        self.asset_record.loc[record_time, "Margin Ratio"] = new_value
                        new_value = order_id
                        self.asset_record.loc[record_time, "Order ID"] = new_value
                        last_asset: float = self.asset_record.loc[
                            last_index, "Result Asset"
                        ]  # type:ignore
                        new_value = last_asset + added_revenue
                        self.asset_record.loc[record_time, "Result Asset"] = new_value
                        if order_id in unique_order_ids:
                            self.asset_record.loc[record_time, "Cause"] = "auto_trade"
                        else:
                            self.asset_record.loc[record_time, "Cause"] = "manual_trade"
                    if not self.asset_record.index.is_monotonic_increasing:
                        self.asset_record = self.asset_record.sort_index()

        # ■■■■■ cancel conflicting orders ■■■■■

        await self.cancel_conflicting_orders()

    async def open_exchange(self, *args, **kwargs):
        symbol = self.viewing_symbol
        webbrowser.open(f"https://www.binance.com/en/futures/{symbol}")

    async def open_futures_wallet_page(self, *args, **kwargs):
        webbrowser.open("https://www.binance.com/en/my/wallet/account/futures")

    async def open_api_management_page(self, *args, **kwargs):
        webbrowser.open("https://www.binance.com/en/my/settings/api-management")

    async def update_keys(self, *args, **kwargs):
        server = kwargs.get("server", "real")

        binance_api = core.window.lineEdit_4.text()
        binance_secret = core.window.lineEdit_6.text()

        new_keys = {}
        new_keys["binance_api"] = binance_api
        new_keys["binance_secret"] = binance_secret

        self.keys = new_keys

        filepath = self.workerpath + "/keys.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(new_keys, indent=4)
            await file.write(content)

        new_keys = {}
        new_keys["server"] = server
        new_keys["binance_api"] = binance_api
        new_keys["binance_secret"] = binance_secret

        self.api_requester.update_keys(new_keys)
        await self.update_user_data_stream()

    async def update_automation_settings(self, *args, **kwargs):
        # ■■■■■ get information about strategy ■■■■■

        strategy_index = core.window.comboBox_2.currentIndex()
        self.automation_settings["strategy_index"] = strategy_index

        asyncio.create_task(self.display_lines())

        # ■■■■■ is automation turned on ■■■■■

        is_checked = core.window.checkBox.isChecked()

        if is_checked:
            self.automation_settings["should_transact"] = True
        else:
            self.automation_settings["should_transact"] = False

        # ■■■■■ save ■■■■■

        filepath = self.workerpath + "/automation_settings.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(self.automation_settings, indent=4)
            await file.write(content)

    async def display_range_information(self, *args, **kwargs):
        task_id = stop_flag.make("display_transaction_range_information")

        symbol = self.viewing_symbol

        range_start_timestamp = core.window.plot_widget.getAxis("bottom").range[0]
        range_start_timestamp = max(range_start_timestamp, 0.0)
        range_start = datetime.fromtimestamp(range_start_timestamp, tz=timezone.utc)

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        range_end_timestamp = core.window.plot_widget.getAxis("bottom").range[1]
        if range_end_timestamp < 0.0:
            # case when pyqtgraph passed negative value because it's too big
            range_end_timestamp = 9223339636.0
        else:
            # maximum value available in pandas
            range_end_timestamp = min(range_end_timestamp, 9223339636.0)
        range_end = datetime.fromtimestamp(range_end_timestamp, tz=timezone.utc)

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        range_length = range_end - range_start
        range_days = range_length.days
        range_hours, remains = divmod(range_length.seconds, 3600)
        range_minutes, remains = divmod(remains, 60)

        if stop_flag.find("display_transaction_range_information", task_id):
            return

        async with datalocks.hold("transactor_unrealized_changes"):
            unrealized_changes = self.unrealized_changes[range_start:range_end].copy()
        async with datalocks.hold("transactor_asset_record"):
            asset_record = self.asset_record[range_start:range_end].copy()

        auto_trade_mask = asset_record["Cause"] == "auto_trade"
        asset_changes = asset_record["Result Asset"].pct_change() + 1
        asset_record = asset_record[auto_trade_mask]
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

        view_range = core.window.plot_widget.getAxis("left").range
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
        core.window.label_8.setText(text)

    async def set_minimum_view_range(self, *args, **kwargs):
        widget = core.window.plot_widget
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore
        widget = core.window.plot_widget_1
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore

    async def display_strategy_index(self, *args, **kwargs):
        strategy_index = self.automation_settings["strategy_index"]
        core.window.comboBox_2.setCurrentIndex(strategy_index)

    async def display_lines(self, *args, **kwargs):
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

        async with datalocks.hold("collector_candle_data"):
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
                async with datalocks.hold("collector_candle_data"):
                    last_index = collector.me.candle_data.index[-1]
                    if last_index == before_moment:
                        break
                await asyncio.sleep(0.1)

        # ■■■■■ get ready for task duration measurement ■■■■■

        task_start_time = datetime.now(timezone.utc)

        # ■■■■■ check things ■■■■■

        symbol = self.viewing_symbol
        strategy_index = self.automation_settings["strategy_index"]
        strategy = strategist.me.strategies[strategy_index]

        # ■■■■■ get light data ■■■■■

        async with datalocks.hold("collector_realtime_data_chunks"):
            before_chunk = collector.me.realtime_data_chunks[-2].copy()
            current_chunk = collector.me.realtime_data_chunks[-1].copy()
        realtime_data = np.concatenate((before_chunk, current_chunk))
        async with datalocks.hold("collector_aggregate_trades"):
            aggregate_trades = collector.me.aggregate_trades.copy()

        # ■■■■■ draw light lines ■■■■■

        # mark price
        data_x = realtime_data["index"].astype(np.int64) / 10**9
        data_y = realtime_data[str((symbol, "Mark Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = core.window.transaction_lines["mark_price"]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # last price
        data_x = aggregate_trades["index"].astype(np.int64) / 10**9
        data_y = aggregate_trades[str((symbol, "Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = core.window.transaction_lines["last_price"]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

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
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # book tickers
        data_x = realtime_data["index"].astype(np.int64) / 10**9
        data_y = realtime_data[str((symbol, "Best Bid Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = core.window.transaction_lines["book_tickers"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        data_x = realtime_data["index"].astype(np.int64) / 10**9
        data_y = realtime_data[str((symbol, "Best Ask Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = core.window.transaction_lines["book_tickers"][1]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

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
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

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

        async with datalocks.hold("collector_candle_data"):
            candle_data = collector.me.candle_data
            candle_data = candle_data[get_from:slice_until][[symbol]]
            candle_data = candle_data.copy()
        async with datalocks.hold("transactor_unrealized_changes"):
            unrealized_changes = self.unrealized_changes.copy()
        async with datalocks.hold("transactor_asset_record"):
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
                if slice_from < observed_until:
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
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

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
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

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
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # wobbles
        sr = candle_data[(symbol, "High")]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["wobbles"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        sr = candle_data[(symbol, "Low")]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["wobbles"][1]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # trade volume
        sr = candle_data[(symbol, "Volume")]
        sr = sr.fillna(value=0)
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["volume"]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # asset
        data_x = asset_record["Result Asset"].index.to_numpy(dtype=np.int64) / 10**9
        data_y = asset_record["Result Asset"].to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["asset"]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # asset with unrealized profit
        sr = asset_record["Result Asset"]
        if len(sr) >= 2:
            sr = sr.resample("10S").ffill()
        unrealized_changes_sr = unrealized_changes.reindex(sr.index)
        sr = sr * (1 + unrealized_changes_sr)
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9 + 5
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["asset_with_unrealized_profit"]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # buy and sell
        df = asset_record.loc[asset_record["Symbol"] == symbol]
        df = df[df["Side"] == "sell"]
        sr = df["Fill Price"]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["sell"]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        df = asset_record.loc[asset_record["Symbol"] == symbol]
        df = df[df["Side"] == "buy"]
        sr = df["Fill Price"]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = core.window.transaction_lines["buy"]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # ■■■■■ record task duration ■■■■■

        duration = (datetime.now(timezone.utc) - task_start_time).total_seconds()
        remember_task_durations.add(task_name, duration)

        # ■■■■■ make indicators ■■■■■

        indicators_script = strategy["indicators_script"]

        indicators = await core.event_loop.run_in_executor(
            core.process_pool,
            functools.partial(
                make_indicators.do,
                target_symbols=[self.viewing_symbol],
                candle_data=candle_data,
                indicators_script=indicators_script,
            ),
        )

        indicators = indicators[slice_from:]

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
                widget.setPen(color)
                widget.setData(data_x, data_y)
                if stop_flag.find(task_name, task_id):
                    return
                await asyncio.sleep(0)
            else:
                if stop_flag.find(task_name, task_id):
                    return
                widget.clear()

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
                widget.setPen(color)
                widget.setData(data_x, data_y)
                if stop_flag.find(task_name, task_id):
                    return
                await asyncio.sleep(0)
            else:
                if stop_flag.find(task_name, task_id):
                    return
                widget.clear()

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
                widget.setPen(color)
                widget.setData(data_x, data_y)
                if stop_flag.find(task_name, task_id):
                    return
                await asyncio.sleep(0)
            else:
                if stop_flag.find(task_name, task_id):
                    return
                widget.clear()

        # ■■■■■ set minimum view range ■■■■■

        await self.set_minimum_view_range()

    async def toggle_frequent_draw(self, *args, **kwargs):
        is_checked = args[0]
        if is_checked:
            self.should_draw_frequently = True
        else:
            self.should_draw_frequently = False
        await self.display_lines()

    async def update_viewing_symbol(self, *args, **kwargs):
        alias = core.window.comboBox_4.currentText()
        symbol = core.window.alias_to_symbol[alias]
        self.viewing_symbol = symbol

        asyncio.create_task(self.display_lines())
        asyncio.create_task(self.display_status_information())
        asyncio.create_task(self.display_range_information())

    async def display_status_information(self, *args, **kwargs):
        # ■■■■■ Display important things first ■■■■■

        time_passed = datetime.now(timezone.utc) - self.account_state["observed_until"]
        if time_passed > timedelta(seconds=30):
            text = (
                "Couldn't get the latest info on your Binance account due to a problem"
                " with your key or connection to the Binance server."
            )
            core.window.label_16.setText(text)
            return

        if not self.secret_memory["is_key_restrictions_satisfied"]:
            text = (
                "API key's restrictions are not satisfied. Auto transaction is"
                " disabled. Go to your Binance API managements webpage to change"
                " the restrictions."
            )
            core.window.label_16.setText(text)
            return

        cumulation_rate = await collector.me.get_candle_data_cumulation_rate()
        if cumulation_rate < 1:
            text = (
                "For auto transaction to work, the past 24 hour accumulation rate of"
                " candle data must be 100%. Auto transaction is disabled."
            )
            core.window.label_16.setText(text)
            return

        # ■■■■■ display assets and positions information ■■■■■

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

        open_orders = self.account_state["open_orders"]
        open_orders_count = len(open_orders[self.viewing_symbol])
        all_open_orders_count = 0
        for symbol_open_orders in open_orders.values():
            all_open_orders_count += len(symbol_open_orders)

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
        text += "Open orders"
        text += f" {open_orders_count}"
        text += f"({all_open_orders_count})"

        core.window.label_16.setText(text)

    async def perform_transaction(self, *args, **kwargs):
        # ■■■■■ stop if internet connection is not present ■■■■

        if not check_internet.connected():
            return

        # ■■■■■ stop if the automation is turned off ■■■■■

        if not self.automation_settings["should_transact"]:
            return

        # ■■■■■ stop if conditions are not met ■■■■■

        if not self.secret_memory["is_key_restrictions_satisfied"]:
            return

        # ■■■■■ stop if the accumulation rate is not 100% ■■■■■

        cumulation_rate = await collector.me.get_candle_data_cumulation_rate()
        if cumulation_rate < 1:
            is_cycle_done = True
            return

        # ■■■■■ play the progress bar ■■■■■

        is_cycle_done = False

        async def play_progress_bar():
            start_time = datetime.now(timezone.utc)
            passed_time = timedelta(seconds=0)
            while passed_time < timedelta(seconds=10):
                passed_time = datetime.now(timezone.utc) - start_time
                if not is_cycle_done:
                    new_value = int(passed_time / timedelta(seconds=10) * 1000)
                else:
                    before_value = core.window.progressBar_2.value()
                    remaining = 1000 - before_value
                    new_value = before_value + math.ceil(remaining * 0.2)

                core.window.progressBar_2.setValue(new_value)
                await asyncio.sleep(0.01)

            core.window.progressBar_2.setValue(0)

        asyncio.create_task(play_progress_bar())

        # ■■■■■ moment ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        # ■■■■■ check if the data exists ■■■■■

        async with datalocks.hold("collector_candle_data"):
            if len(collector.me.candle_data) == 0:
                # case when the app is executed for the first time
                return

        # ■■■■■ wait for the latest data to be added ■■■■■

        for _ in range(50):
            async with datalocks.hold("collector_candle_data"):
                last_index = collector.me.candle_data.index[-1]
                if last_index == before_moment:
                    break
            await asyncio.sleep(0.1)

        # ■■■■■ get the candle data ■■■■■

        slice_from = datetime.now(timezone.utc) - timedelta(days=7)
        async with datalocks.hold("collector_candle_data"):
            df = collector.me.candle_data
            partial_candle_data = df[slice_from:].copy()

        # ■■■■■ make decision ■■■■■

        target_symbols = user_settings.get_data_settings()["target_symbols"]

        strategy_index = self.automation_settings["strategy_index"]
        strategy = strategist.me.strategies[strategy_index]

        indicators_script = strategy["indicators_script"]

        indicators = await core.event_loop.run_in_executor(
            core.process_pool,
            functools.partial(
                make_indicators.do,
                target_symbols=target_symbols,
                candle_data=partial_candle_data,
                indicators_script=indicators_script,
            ),
        )

        current_candle_data = partial_candle_data.to_records()[-1]
        current_indicators = indicators.to_records()[-1]
        decision_script = strategy["decision_script"]

        decision, scribbles = await core.event_loop.run_in_executor(
            core.process_pool,
            functools.partial(
                decide.choose,
                target_symbols=target_symbols,
                current_moment=current_moment,
                current_candle_data=current_candle_data,
                current_indicators=current_indicators,
                account_state=copy.deepcopy(self.account_state),
                scribbles=self.scribbles,
                decision_script=decision_script,
            ),
        )
        self.scribbles = scribbles

        # ■■■■■ record task duration ■■■■■

        is_cycle_done = True
        duration = (datetime.now(timezone.utc) - current_moment).total_seconds()
        remember_task_durations.add("perform_transaction", duration)

        # ■■■■■ place order ■■■■■

        await self.place_orders(decision)

    async def display_day_range(self, *args, **kwargs):
        range_start = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
        range_end = datetime.now(timezone.utc).timestamp()
        widget = core.window.plot_widget
        widget.setXRange(range_start, range_end)

    async def match_graph_range(self, *args, **kwargs):
        range_start = core.window.plot_widget_2.getAxis("bottom").range[0]
        range_end = core.window.plot_widget_2.getAxis("bottom").range[1]
        widget = core.window.plot_widget
        widget.setXRange(range_start, range_end, padding=0)  # type:ignore

    async def update_mode_settings(self, *args, **kwargs):
        desired_leverage = core.window.spinBox.value()
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
            answer = await core.window.ask(question)
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
                await core.window.ask(question)

        # ■■■■■ save ■■■■■

        filepath = self.workerpath + "/mode_settings.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(self.mode_settings, indent=4)
            await file.write(content)

    async def watch_binance(self, *args, **kwargs):
        # ■■■■■ check internet connection ■■■■■

        if not check_internet.connected():
            return

        # ■■■■■ moment ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        # ■■■■■ request exchange information ■■■■■

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
            response = await self.api_requester.binance(
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
            response = await self.api_requester.binance(
                http_method="GET",
                path="/fapi/v2/account",
                payload=payload,
            )
            about_account = response
        except ApiRequestError:
            # when the key is not ready
            return

        about_open_orders = {}

        async def job(symbol):
            payload = {
                "symbol": symbol,
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
            response = await self.api_requester.binance(
                http_method="GET",
                path="/fapi/v1/openOrders",
                payload=payload,
            )
            about_open_orders[symbol] = response

        await asyncio.gather(
            *[
                job(symbol)
                for symbol in user_settings.get_data_settings()["target_symbols"]
            ]
        )

        # ■■■■■ update account state ■■■■■

        # observed until
        self.account_state["observed_until"] = current_moment

        # wallet_balance
        about_asset = {}
        for about_asset in about_account["assets"]:
            if about_asset["asset"] == user_settings.get_data_settings()["asset_token"]:
                break
        wallet_balance = float(about_asset["walletBalance"])
        self.account_state["wallet_balance"] = wallet_balance

        # positions
        for symbol in user_settings.get_data_settings()["target_symbols"]:
            about_position = {}
            for about_position in about_account["positions"]:
                if about_position["symbol"] == symbol:
                    break

            if float(about_position["notional"]) > 0:
                direction = "long"
            elif float(about_position["notional"]) < 0:
                direction = "short"
            else:
                direction = "none"

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
            about_position = {}
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
                        else:
                            raise ValueError("Cannot order with this side")
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
                    else:
                        raise ValueError("Cannot order with this side")
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
                        else:
                            raise ValueError("Cannot order with this side")
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
                    else:
                        raise ValueError("Cannot order with this side")
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
                        raise ValueError("Cannot order with this side")
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
            about_position = {}
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

        async with datalocks.hold("transactor_unrealized_changes"):
            self.unrealized_changes[before_moment] = unrealized_change
            if not self.unrealized_changes.index.is_monotonic_increasing:
                self.unrealized_changes = self.unrealized_changes.sort_index()

        # ■■■■■ make an asset trace if it's blank ■■■■■

        async with datalocks.hold("transactor_asset_record"):
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

        # ■■■■■ when the wallet balance changed for no good reason ■■■■■

        for about_asset in about_account["assets"]:
            if about_asset["asset"] == user_settings.get_data_settings()["asset_token"]:
                break
        wallet_balance = float(about_asset["walletBalance"])

        async with datalocks.hold("transactor_asset_record"):
            last_index = self.asset_record.index[-1]
            last_asset: float = self.asset_record.loc[last_index, "Result Asset"]  # type:ignore

        if wallet_balance == 0:
            pass
        elif abs(wallet_balance - last_asset) / wallet_balance > 10**-9:
            # when the difference is bigger than a billionth
            # referal fee, funding fee, wallet transfer, etc..
            async with datalocks.hold("transactor_asset_record"):
                current_time = datetime.now(timezone.utc)
                self.asset_record.loc[current_time, "Cause"] = "other"
                self.asset_record.loc[current_time, "Result Asset"] = wallet_balance
                if not self.asset_record.index.is_monotonic_increasing:
                    self.asset_record = self.asset_record.sort_index()
        else:
            # when the difference is small enough to consider as an numeric error
            async with datalocks.hold("transactor_asset_record"):
                last_index = self.asset_record.index[-1]
                self.asset_record.loc[last_index, "Result Asset"] = wallet_balance

        # ■■■■■ correct mode of the account market if automation is turned on ■■■■■

        if self.automation_settings["should_transact"]:

            async def job_1(symbol):
                about_position = {}
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
                    await self.api_requester.binance(
                        http_method="POST",
                        path="/fapi/v1/leverage",
                        payload=payload,
                    )

            await asyncio.gather(
                *[
                    job_1(symbol)
                    for symbol in user_settings.get_data_settings()["target_symbols"]
                ]
            )

            async def job_2(symbol):
                about_position = {}
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
                        await self.place_orders(decision)

                    # change to crossed margin mode
                    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                    payload = {
                        "symbol": symbol,
                        "timestamp": timestamp,
                        "marginType": "CROSSED",
                    }
                    await self.api_requester.binance(
                        http_method="POST",
                        path="/fapi/v1/marginType",
                        payload=payload,
                    )

            await asyncio.gather(
                *[
                    job_2(symbol)
                    for symbol in user_settings.get_data_settings()["target_symbols"]
                ]
            )

            try:
                timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                payload = {
                    "timestamp": timestamp,
                    "multiAssetsMargin": "false",
                }
                await self.api_requester.binance(
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
                await self.api_requester.binance(
                    http_method="POST",
                    path="/fapi/v1/positionSide/dual",
                    payload=payload,
                )
            except ApiRequestError:
                pass

        # ■■■■■ check API key restrictions ■■■■■

        payload = {
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        response = await self.api_requester.binance(
            http_method="GET",
            path="/sapi/v1/account/apiRestrictions",
            payload=payload,
            server="spot",
        )
        api_restrictions = response

        is_satisfied = True
        enable_required_restrictions = [
            "enableFutures",
        ]
        for restriction_name in enable_required_restrictions:
            is_enabled = api_restrictions[restriction_name]
            if not is_enabled:
                is_satisfied = False
        self.secret_memory["is_key_restrictions_satisfied"] = is_satisfied

    async def place_orders(self, *args, **kwargs):
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

            async with datalocks.hold("collector_aggregate_trades"):
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
                    side = "NONE"
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
                    new_order_side = "NONE"
                    new_order_type = "NONE"
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
                    new_order_side = "NONE"
                    new_order_type = "NONE"
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

        async def job_1(payload):
            response = await self.api_requester.binance(
                http_method="POST",
                path="/fapi/v1/order",
                payload=payload,
            )
            order_symbol = response["symbol"]
            order_id = response["orderId"]
            timestamp = response["updateTime"] / 1000
            update_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            async with datalocks.hold("transactor_auto_order_record"):
                while update_time in self.auto_order_record.index:
                    update_time += timedelta(milliseconds=1)
                self.auto_order_record.loc[update_time, "Symbol"] = order_symbol
                self.auto_order_record.loc[update_time, "Order ID"] = order_id
                if not self.auto_order_record.index.is_monotonic_increasing:
                    self.auto_order_record = self.auto_order_record.sort_index()

        await asyncio.gather(*[job_1(order) for order in new_orders])

        async def job_2(payload):
            await self.api_requester.binance(
                http_method="DELETE",
                path="/fapi/v1/allOpenOrders",
                payload=payload,
            )

        await asyncio.gather(*[job_2(order) for order in new_orders])

        # ■■■■■ record task duration ■■■■■

        duration = datetime.now(timezone.utc) - task_start_time
        duration = duration.total_seconds()
        remember_task_durations.add("place_orders", duration)

    async def clear_positions_and_open_orders(self, *args, **kwargs):
        decision = {}
        for symbol in user_settings.get_data_settings()["target_symbols"]:
            decision[symbol] = {
                "cancel_all": {},
                "now_close": {},
            }
        await self.place_orders(decision)

    async def cancel_conflicting_orders(self, *args, **kwargs):
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

        async def job(conflicting_order_tuple):
            try:
                payload = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "symbol": conflicting_order_tuple[0],
                    "orderId": conflicting_order_tuple[1],
                }
                await self.api_requester.binance(
                    http_method="DELETE",
                    path="/fapi/v1/order",
                    payload=payload,
                )
            except ApiRequestError:
                pass

        await asyncio.gather(*[job(conflict) for conflict in conflicting_order_tuples])

    async def pan_view_range(self, *args, **kwargs):
        if not self.should_draw_frequently:
            return

        widget = core.window.plot_widget
        before_range = widget.getAxis("bottom").range
        range_start = before_range[0]
        range_end = before_range[1]

        if range_end - range_start < 6 * 60 * 60:  # six hours
            return

        widget.setXRange(range_start + 10, range_end + 10, padding=0)  # type:ignore

    async def show_raw_account_state_object(self, *args, **kwargs):
        text = ""

        time = datetime.now(timezone.utc)
        time_text = time.strftime("%Y-%m-%d %H:%M:%S")
        text += f"At UTC {time_text}"

        text += "\n\n"
        text += json.dumps(self.account_state, indent=4, default=str)

        formation = [
            "This is the raw account state object",
            LongTextView,
            True,
            [text],
        ]
        await core.window.overlap(formation)


me = None


def bring_to_life():
    global me
    me = Transactor()
