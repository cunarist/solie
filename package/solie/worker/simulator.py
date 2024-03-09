import asyncio
import math
import os
import pickle
import re
from datetime import datetime, timedelta, timezone
from typing import List

import aiofiles
import numpy as np
import pandas as pd
from scipy.signal import find_peaks

import solie
from solie.definition.rw_lock import RWLock
from solie.parallel import go
from solie.utility import (
    make_indicators,
    simply_format,
    simulate_chunk,
    sort_pandas,
    standardize,
    stop_flag,
    user_settings,
)


class Simulator:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = user_settings.get_app_settings()["datapath"] + "/simulator"
        os.makedirs(self.workerpath, exist_ok=True)

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {}

        # ■■■■■ remember and display ■■■■■

        self.viewing_symbol = user_settings.get_data_settings()["target_symbols"][0]
        self.should_draw_all_years = False

        self.about_viewing = None

        self.calculation_settings = {
            "year": datetime.now(timezone.utc).year,
            "strategy_index": 0,
        }
        self.presentation_settings = {
            "maker_fee": 0.02,
            "taker_fee": 0.04,
            "leverage": 1,
        }

        self.raw_account_state = standardize.account_state()
        self.raw_scribbles = {}
        self.raw_asset_record = RWLock(standardize.asset_record())
        self.raw_unrealized_changes = RWLock(standardize.unrealized_changes())

        self.account_state = standardize.account_state()
        self.scribbles = {}
        self.asset_record = RWLock(standardize.asset_record())
        self.unrealized_changes = RWLock(standardize.unrealized_changes())

        # ■■■■■ repetitive schedules ■■■■■

        solie.window.scheduler.add_job(
            self.display_available_years,
            trigger="cron",
            hour="*",
        )
        solie.window.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            hour="*",
            kwargs={"periodic": True},
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = {}

        # ■■■■■ invoked by the internet connection status change  ■■■■■

    async def load(self, *args, **kwargs):
        text = "Nothing drawn"
        solie.window.label_19.setText(text)

    async def update_viewing_symbol(self, *args, **kwargs):
        alias = solie.window.comboBox_6.currentText()
        symbol = solie.window.alias_to_symbol[alias]
        self.viewing_symbol = symbol

        await self.display_lines()

    async def update_calculation_settings(self, *args, **kwargs):
        text = solie.window.comboBox_5.currentText()
        if text == "":
            return
        from_year = self.calculation_settings["year"]
        to_year = int(text)
        self.calculation_settings["year"] = to_year
        if from_year != to_year:
            asyncio.create_task(self.display_year_range())

        index = solie.window.comboBox.currentIndex()
        self.calculation_settings["strategy_index"] = index

        await self.display_lines()

    async def update_presentation_settings(self, *args, **kwargs):
        input_value = solie.window.spinBox_2.value()
        self.presentation_settings["leverage"] = input_value
        input_value = solie.window.doubleSpinBox.value()
        self.presentation_settings["taker_fee"] = input_value
        input_value = solie.window.doubleSpinBox_2.value()
        self.presentation_settings["maker_fee"] = input_value
        await self.present()

    async def display_lines(self, *args, **kwargs):
        # ■■■■■ start the task ■■■■■

        periodic = kwargs.get("periodic", False)
        frequent = kwargs.get("frequent", False)
        only_light_lines = kwargs.get("only_light_lines", False)

        if only_light_lines:
            task_name = "display_light_simulation_lines"
        else:
            task_name = "display_all_simulation_lines"

        task_id = stop_flag.make(task_name)

        # ■■■■■ check drawing mode ■■■■■

        should_draw_all_years = self.should_draw_all_years

        if frequent:
            pass

        # ■■■■■ check if the data exists ■■■■■

        async with solie.window.collector.candle_data.read_lock as cell:
            if len(cell.data) == 0:
                return

        # ■■■■■ wait for the latest data to be added ■■■■■

        current_moment = datetime.now(timezone.utc).replace(microsecond=0)
        current_moment = current_moment - timedelta(seconds=current_moment.second % 10)
        before_moment = current_moment - timedelta(seconds=10)

        if periodic:
            for _ in range(50):
                if stop_flag.find(task_name, task_id):
                    return
                async with solie.window.collector.candle_data.read_lock as cell:
                    last_index = cell.data.index[-1]
                    if last_index == before_moment:
                        break
                await asyncio.sleep(0.1)

        # ■■■■■ get ready for task duration measurement ■■■■■

        pass

        # ■■■■■ check things ■■■■■

        symbol = self.viewing_symbol
        strategy_index = self.calculation_settings["strategy_index"]
        strategy = solie.window.strategist.strategies[strategy_index]

        # ■■■■■ get light data ■■■■■

        async with solie.window.collector.realtime_data_chunks.read_lock as cell:
            before_chunk = cell.data[-2].copy()
            current_chunk = cell.data[-1].copy()
        realtime_data = np.concatenate((before_chunk, current_chunk))
        async with solie.window.collector.aggregate_trades.read_lock as cell:
            aggregate_trades = cell.data.copy()

        # ■■■■■ draw light lines ■■■■■

        # mark price
        data_x = realtime_data["index"].astype(np.int64) / 10**9
        data_y = realtime_data[str((symbol, "Mark Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = solie.window.simulation_lines["mark_price"][0]
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
        widget = solie.window.simulation_lines["last_price"][0]
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
        widget = solie.window.simulation_lines["last_volume"][0]
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
        widget = solie.window.simulation_lines["book_tickers"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        data_x = realtime_data["index"].astype(np.int64) / 10**9
        data_y = realtime_data[str((symbol, "Best Ask Price"))]
        mask = data_y != 0
        data_y = data_y[mask]
        data_x = data_x[mask]
        widget = solie.window.simulation_lines["book_tickers"][1]
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
        widget = solie.window.simulation_lines["entry_price"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # ■■■■■ record task duration ■■■■■

        pass

        # ■■■■■ stop if the target is only light lines ■■■■■

        if only_light_lines:
            return

        # ■■■■■ set range of heavy data ■■■■■

        if should_draw_all_years:
            years = [
                int(simply_format.numeric(filename))
                for filename in os.listdir(solie.window.collector.workerpath)
                if filename.startswith("candle_data_") and filename.endswith(".pickle")
            ]
            slice_from = datetime.fromtimestamp(0, tz=timezone.utc)
            slice_until = datetime.now(timezone.utc)
            slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
        else:
            year = self.calculation_settings["year"]
            years = [year]
            slice_from = datetime(year, 1, 1, tzinfo=timezone.utc)
            if year == datetime.now(timezone.utc).year:
                slice_until = datetime.now(timezone.utc)
                slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
            else:
                slice_until = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        slice_until -= timedelta(seconds=1)

        # ■■■■■ get heavy data ■■■■■

        divided_datas: List[pd.DataFrame] = []
        for year in years:
            filepath = f"{solie.window.collector.workerpath}/candle_data_{year}.pickle"
            more_df = await go(pd.read_pickle, filepath)
            divided_datas.append(more_df)
        candle_data = await go(pd.concat, divided_datas)
        if not candle_data.index.is_monotonic_increasing:
            candle_data = await go(sort_pandas.data_frame, candle_data)
        async with self.unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data.copy()
        async with self.asset_record.read_lock as cell:
            if len(cell.data) > 0:
                last_asset = cell.data.iloc[-1]["Result Asset"]
            else:
                last_asset = None
            before_record = cell.data[:slice_from]
            if len(before_record) > 0:
                before_asset = before_record.iloc[-1]["Result Asset"]
            else:
                before_asset = None
            asset_record = cell.data[slice_from:].copy()

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
                    if not asset_record.index.is_monotonic_increasing:
                        asset_record = await go(sort_pandas.data_frame, asset_record)

        # add the left end

        if before_asset is not None:
            asset_record.loc[slice_from, "Cause"] = "other"
            asset_record.loc[slice_from, "Result Asset"] = before_asset
            if not asset_record.index.is_monotonic_increasing:
                asset_record = await go(sort_pandas.data_frame, asset_record)

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
        widget = solie.window.simulation_lines["price_rise"][0]
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
        widget = solie.window.simulation_lines["price_fall"][0]
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
        widget = solie.window.simulation_lines["price_stay"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # wobbles
        sr = candle_data[(symbol, "High")]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = solie.window.simulation_lines["wobbles"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        sr = candle_data[(symbol, "Low")]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = solie.window.simulation_lines["wobbles"][1]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # trade volume
        sr = candle_data[(symbol, "Volume")]
        sr = sr.fillna(value=0)
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = solie.window.simulation_lines["volume"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # asset
        data_x = asset_record["Result Asset"].index.to_numpy(dtype=np.int64) / 10**9
        data_y = asset_record["Result Asset"].to_numpy(dtype=np.float32)
        widget = solie.window.simulation_lines["asset"][0]
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
        widget = solie.window.simulation_lines["asset_with_unrealized_profit"][0]
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
        widget = solie.window.simulation_lines["sell"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        df = asset_record.loc[asset_record["Symbol"] == symbol]
        df = df[df["Side"] == "buy"]
        sr = df["Fill Price"]
        data_x = sr.index.to_numpy(dtype=np.int64) / 10**9
        data_y = sr.to_numpy(dtype=np.float32)
        widget = solie.window.simulation_lines["buy"][0]
        widget.setData(data_x, data_y)
        if stop_flag.find(task_name, task_id):
            return
        await asyncio.sleep(0)

        # ■■■■■ record task duration ■■■■■

        pass

        # ■■■■■ make indicators ■■■■■

        indicators_script = strategy["indicators_script"]

        indicators = await go(
            make_indicators.do,
            target_symbols=[self.viewing_symbol],
            candle_data=candle_data,
            indicators_script=indicators_script,
        )

        indicators = indicators[slice_from:]

        # ■■■■■ draw strategy lines ■■■■■

        # price indicators
        df = indicators[symbol]["Price"]
        data_x = df.index.to_numpy(dtype=np.int64) / 10**9
        data_x += 5
        line_list = solie.window.simulation_lines["price_indicators"]
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
        line_list = solie.window.simulation_lines["volume_indicators"]
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
        line_list = solie.window.simulation_lines["abstract_indicators"]
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

    async def erase(self, *args, **kwargs):
        self.raw_account_state = standardize.account_state()
        self.raw_scribbles = {}
        self.raw_asset_record = RWLock(standardize.asset_record())
        self.raw_unrealized_changes = RWLock(standardize.unrealized_changes())
        self.about_viewing = None

        await self.present()

    async def display_available_years(self, *args, **kwargs):
        years = [
            int(simply_format.numeric(filename))
            for filename in os.listdir(solie.window.collector.workerpath)
            if filename.startswith("candle_data_") and filename.endswith(".pickle")
        ]
        years.sort(reverse=True)

        widget = solie.window.comboBox_5
        choices = [int(widget.itemText(i)) for i in range(widget.count())]
        choices.sort(reverse=True)

        if years != choices:
            # if it's changed
            solie.window.comboBox_5.clear()
            solie.window.comboBox_5.addItems([str(y) for y in years])

    async def simulate_only_visible(self, *args, **kwargs):
        await self.calculate(only_visible=True)

    async def display_range_information(self, *args, **kwargs):
        task_id = stop_flag.make("display_simulation_range_information")

        symbol = self.viewing_symbol

        range_start_timestamp = solie.window.plot_widget_2.getAxis("bottom").range[0]
        range_start_timestamp = max(range_start_timestamp, 0.0)
        range_start = datetime.fromtimestamp(range_start_timestamp, tz=timezone.utc)

        if stop_flag.find("display_simulation_range_information", task_id):
            return

        range_end_timestamp = solie.window.plot_widget_2.getAxis("bottom").range[1]
        if range_end_timestamp < 0:
            # case when pyqtgraph passed negative value because it's too big
            range_end_timestamp = 9223339636
        else:
            # maximum value available in pandas
            range_end_timestamp = min(range_end_timestamp, 9223339636.0)
        range_end = datetime.fromtimestamp(range_end_timestamp, tz=timezone.utc)

        if stop_flag.find("display_simulation_range_information", task_id):
            return

        range_length = range_end - range_start
        range_days = range_length.days
        range_hours, remains = divmod(range_length.seconds, 3600)
        range_minutes, remains = divmod(remains, 60)

        if stop_flag.find("display_simulation_range_information", task_id):
            return

        async with self.unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data[range_start:range_end].copy()
        async with self.asset_record.read_lock as cell:
            asset_record = cell.data[range_start:range_end].copy()

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

        if stop_flag.find("display_simulation_range_information", task_id):
            return

        view_range = solie.window.plot_widget_2.getAxis("left").range
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
        solie.window.label_13.setText(text)

    async def set_minimum_view_range(self, *args, **kwargs):
        widget = solie.window.plot_widget_2
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore
        widget = solie.window.plot_widget_3
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore

    async def calculate(self, *args, **kwargs):
        task_id = stop_flag.make("calculate_simulation")

        only_visible = kwargs.get("only_visible", False)

        prepare_step = 0
        calculate_step = 0

        async def play_progress_bar():
            while True:
                if stop_flag.find("calculate_simulation", task_id):
                    solie.window.progressBar_4.setValue(0)
                    solie.window.progressBar.setValue(0)
                    return
                else:
                    if prepare_step == 6 and calculate_step == 1000:
                        is_progressbar_filled = True
                        progressbar_value = solie.window.progressBar_4.value()
                        if progressbar_value < 1000:
                            is_progressbar_filled = False
                        progressbar_value = solie.window.progressBar.value()
                        if progressbar_value < 1000:
                            is_progressbar_filled = False
                        if is_progressbar_filled:
                            await asyncio.sleep(0.1)
                            solie.window.progressBar_4.setValue(0)
                            solie.window.progressBar.setValue(0)
                            return
                    widget = solie.window.progressBar_4
                    before_value = widget.value()
                    if before_value < 1000:
                        remaining = math.ceil(1000 / 6 * prepare_step) - before_value
                        new_value = before_value + math.ceil(remaining * 0.2)
                        widget.setValue(new_value)
                    widget = solie.window.progressBar
                    before_value = widget.value()
                    if before_value < 1000:
                        remaining = calculate_step - before_value
                        new_value = before_value + math.ceil(remaining * 0.2)
                        widget.setValue(new_value)
                    await asyncio.sleep(0.01)

        asyncio.create_task(play_progress_bar())

        prepare_step = 1

        # ■■■■■ default values and the strategy ■■■■■

        year = self.calculation_settings["year"]
        strategy_index = self.calculation_settings["strategy_index"]

        strategy = solie.window.strategist.strategies[strategy_index]
        strategy_code_name = strategy["code_name"]
        strategy_version = strategy["version"]
        should_parallelize = strategy["parallelized_simulation"]
        chunk_length = strategy["chunk_division"]

        path_start = f"{self.workerpath}/{strategy_code_name}_{strategy_version}_{year}"
        asset_record_path = path_start + "_asset_record.pickle"
        unrealized_changes_path = path_start + "_unrealized_changes.pickle"
        scribbles_path = path_start + "_scribbles.pickle"
        account_state_path = path_start + "_account_state.pickle"
        virtual_state_path = path_start + "_virtual_state.pickle"

        target_symbols = user_settings.get_data_settings()["target_symbols"]

        prepare_step = 2

        # ■■■■■ Get data ■■■■■

        # Set ranges
        slice_from = datetime(year, 1, 1, tzinfo=timezone.utc)

        if year == datetime.now(timezone.utc).year:
            slice_until = datetime.now(timezone.utc)
            slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
        else:
            slice_until = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        slice_until -= timedelta(seconds=1)

        # Get the candle data of this year.
        filepath = f"{solie.window.collector.workerpath}/candle_data_{year}.pickle"
        year_candle_data: pd.DataFrame = await go(pd.read_pickle, filepath)

        # Interpolate so that there's no inappropriate holes.
        year_candle_data = year_candle_data.interpolate()

        prepare_step = 3

        # ■■■■■ prepare data and calculation range ■■■■■

        blank_asset_record = standardize.asset_record()
        blank_unrealized_changes = standardize.unrealized_changes()
        blank_scribbles = {}
        blank_account_state = standardize.account_state()
        blank_virtual_state = {
            "available_balance": 1,
            "locations": {},
            "placements": {},
        }
        for symbol in target_symbols:
            blank_virtual_state["locations"][symbol] = {
                "amount": 0,
                "entry_price": 0,
            }
            blank_virtual_state["placements"][symbol] = {}

        prepare_step = 4

        if only_visible:
            # when calculating only on visible range

            previous_asset_record = blank_asset_record.copy()
            previous_unrealized_changes = blank_unrealized_changes.copy()
            previous_scribbles = blank_scribbles.copy()
            previous_account_state = blank_account_state.copy()
            previous_virtual_state = blank_virtual_state.copy()

            view_range = solie.window.plot_widget_2.getAxis("bottom").range
            view_start = datetime.fromtimestamp(view_range[0], tz=timezone.utc)
            view_end = datetime.fromtimestamp(view_range[1], tz=timezone.utc)

            if self.should_draw_all_years:
                calculate_from = view_start
                calculate_until = view_end
            else:
                calculate_from = max(view_start, slice_from)
                calculate_until = min(view_end, slice_until)

        else:
            # when calculating properly
            try:
                filepath = asset_record_path
                previous_asset_record = await go(pd.read_pickle, filepath)
                filepath = unrealized_changes_path
                previous_unrealized_changes = await go(pd.read_pickle, filepath)
                async with aiofiles.open(scribbles_path, "rb") as file:
                    content = await file.read()
                    previous_scribbles = pickle.loads(content)
                async with aiofiles.open(account_state_path, "rb") as file:
                    content = await file.read()
                    previous_account_state = pickle.loads(content)
                async with aiofiles.open(virtual_state_path, "rb") as file:
                    content = await file.read()
                    previous_virtual_state = pickle.loads(content)

                calculate_from = previous_account_state["observed_until"]
                calculate_until = slice_until
            except FileNotFoundError:
                previous_asset_record = blank_asset_record.copy()
                previous_unrealized_changes = blank_unrealized_changes.copy()
                previous_scribbles = blank_scribbles.copy()
                previous_account_state = blank_account_state.copy()
                previous_virtual_state = blank_virtual_state.copy()

                calculate_from = slice_from
                calculate_until = slice_until

        should_calculate = calculate_from < calculate_until
        if len(previous_asset_record) == 0:
            previous_asset_record.loc[calculate_from, "Cause"] = "other"
            previous_asset_record.loc[calculate_from, "Result Asset"] = float(1)

        prepare_step = 5

        # ■■■■■ prepare per chunk data ■■■■■

        calculation_input_data = []
        progress_list = solie.parallel.communicator.list([0])

        if should_calculate:
            decision_script = strategy["decision_script"]
            indicators_script = strategy["indicators_script"]

            # a little more data for generation
            provide_from = calculate_from - timedelta(days=7)
            year_indicators = await go(
                make_indicators.do,
                target_symbols=target_symbols,
                candle_data=year_candle_data[provide_from:calculate_until],
                indicators_script=indicators_script,
            )

            # range cut
            needed_candle_data = year_candle_data[calculate_from:calculate_until]
            needed_index = needed_candle_data.index
            needed_indicators = year_indicators.reindex(needed_index)

            if should_parallelize:
                division = timedelta(days=chunk_length)
                chunk_candle_data_list = [
                    chunk_candle_data
                    for _, chunk_candle_data in needed_candle_data.groupby(
                        pd.Grouper(freq=division, origin="epoch")  # type:ignore
                    )
                ]

                chunk_count = len(chunk_candle_data_list)
                progress_list = solie.parallel.communicator.list([0] * chunk_count)

                for turn, chunk_candle_data in enumerate(chunk_candle_data_list):
                    chunk_index = chunk_candle_data.index
                    chunk_indicators = needed_indicators.reindex(chunk_index)
                    chunk_asset_record = previous_asset_record.iloc[0:0]
                    chunk_unrealized_changes = previous_unrealized_changes.iloc[0:0]
                    first_timestamp = chunk_index[0].timestamp()
                    division_seconds = chunk_length * 24 * 60 * 60
                    if turn == 0 and first_timestamp % division_seconds != 0:
                        # when this is the firstmost chunk of calculation
                        # and also chunk calculation was partially done before
                        chunk_scribbles = previous_scribbles
                        chunk_account_state = previous_account_state
                        chunk_virtual_state = previous_virtual_state
                    else:
                        chunk_scribbles = blank_scribbles
                        chunk_account_state = blank_account_state
                        chunk_virtual_state = blank_virtual_state

                    dataset = {
                        "progress_list": progress_list,
                        "target_progress": turn,
                        "target_symbols": target_symbols,
                        "calculation_index": chunk_index,
                        "chunk_candle_data": chunk_candle_data,
                        "chunk_indicators": chunk_indicators,
                        "chunk_asset_record": chunk_asset_record,
                        "chunk_unrealized_changes": chunk_unrealized_changes,
                        "chunk_scribbles": chunk_scribbles,
                        "chunk_account_state": chunk_account_state,
                        "chunk_virtual_state": chunk_virtual_state,
                        "decision_script": decision_script,
                    }
                    calculation_input_data.append(dataset)

            else:
                dataset = {
                    "progress_list": progress_list,
                    "target_progress": 0,
                    "target_symbols": target_symbols,
                    "calculation_index": needed_index,
                    "chunk_candle_data": needed_candle_data,
                    "chunk_indicators": needed_indicators,
                    "chunk_asset_record": previous_asset_record,
                    "chunk_unrealized_changes": previous_unrealized_changes,
                    "chunk_scribbles": previous_scribbles,
                    "chunk_account_state": previous_account_state,
                    "chunk_virtual_state": previous_virtual_state,
                    "decision_script": decision_script,
                }
                calculation_input_data.append(dataset)

        prepare_step = 6

        # ■■■■■ calculate ■■■■■

        calculation_output_data = []

        if should_calculate:
            futures = [
                go(simulate_chunk.do, input_data)
                for input_data in calculation_input_data
            ]
            gathered = asyncio.gather(*futures)

            total_seconds = (calculate_until - calculate_from).total_seconds()

            async def update_calculation_step():
                nonlocal calculate_step
                while True:
                    if stop_flag.find("calculate_simulation", task_id):
                        return
                    if gathered.done():
                        return
                    total_progress = sum(progress_list)
                    calculate_step = math.ceil(total_progress * 1000 / total_seconds)
                    await asyncio.sleep(0.01)

            asyncio.create_task(update_calculation_step())

            calculation_output_data = await gathered

        calculate_step = 1000

        # ■■■■■ get calculation result ■■■■■

        if should_calculate:
            asset_record = previous_asset_record
            for chunk_ouput_data in calculation_output_data:
                chunk_asset_record = chunk_ouput_data["chunk_asset_record"]
                concat_data = [asset_record, chunk_asset_record]
                asset_record = pd.concat(concat_data)
            mask = ~asset_record.index.duplicated()
            asset_record = asset_record[mask]
            if not asset_record.index.is_monotonic_increasing:
                asset_record = await go(sort_pandas.data_frame, asset_record)

            unrealized_changes = previous_unrealized_changes
            for chunk_ouput_data in calculation_output_data:
                chunk_unrealized_changes = chunk_ouput_data["chunk_unrealized_changes"]
                concat_data = [unrealized_changes, chunk_unrealized_changes]
                unrealized_changes: pd.Series = pd.concat(concat_data)
            mask = ~unrealized_changes.index.duplicated()
            unrealized_changes = unrealized_changes[mask]
            if not unrealized_changes.index.is_monotonic_increasing:
                unrealized_changes = await go(sort_pandas.series, unrealized_changes)

            scribbles = calculation_output_data[-1]["chunk_scribbles"]
            account_state = calculation_output_data[-1]["chunk_account_state"]
            virtual_state = calculation_output_data[-1]["chunk_virtual_state"]

        else:
            asset_record = previous_asset_record
            unrealized_changes = previous_unrealized_changes
            scribbles = previous_scribbles
            account_state = previous_account_state
            virtual_state = previous_virtual_state

        # ■■■■■ remember and present ■■■■■

        self.raw_asset_record = RWLock(asset_record)
        self.raw_unrealized_changes = RWLock(unrealized_changes)
        self.raw_scribbles = scribbles
        self.raw_account_state = account_state
        self.about_viewing = {
            "year": year,
            "strategy_code_name": strategy_code_name,
            "strategy_version": strategy_version,
        }
        await self.present()

        # ■■■■■ save if properly calculated ■■■■■

        if not only_visible and should_calculate:
            await go(asset_record.to_pickle, asset_record_path)
            await go(unrealized_changes.to_pickle, unrealized_changes_path)
            async with aiofiles.open(scribbles_path, "wb") as file:
                content = pickle.dumps(scribbles)
                await file.write(content)
            async with aiofiles.open(account_state_path, "wb") as file:
                content = pickle.dumps(account_state)
                await file.write(content)
            async with aiofiles.open(virtual_state_path, "wb") as file:
                content = pickle.dumps(virtual_state)
                await file.write(content)

    async def present(self, *args, **kwargs):
        maker_fee = self.presentation_settings["maker_fee"]
        taker_fee = self.presentation_settings["taker_fee"]
        leverage = self.presentation_settings["leverage"]

        async with self.raw_asset_record.read_lock as cell:
            asset_record = cell.data.copy()

        async with self.raw_unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data.copy()

        scribbles = self.raw_scribbles.copy()
        account_state = self.raw_account_state.copy()

        # ■■■■■ get strategy details ■■■■

        if self.about_viewing is None:
            should_parallelize = False
            chunk_length = 0
        else:
            strategy_index = self.calculation_settings["strategy_index"]
            strategy = solie.window.strategist.strategies[strategy_index]
            should_parallelize = strategy["parallelized_simulation"]
            chunk_length = strategy["chunk_division"]

        # ■■■■■ apply other factors to the asset trace ■■■■

        if should_parallelize:
            division = timedelta(days=chunk_length)
            grouper = pd.Grouper(freq=division, origin="epoch")  # type:ignore
            grouped = asset_record.groupby(grouper)
            chunk_asset_record_list = [r.dropna() for _, r in grouped]
            chunk_count = len(chunk_asset_record_list)

        else:
            chunk_asset_record_list = [asset_record]
            chunk_count = 1

        chunk_asset_changes_list = []
        for turn in range(chunk_count):
            chunk_asset_record = chunk_asset_record_list[turn]
            # leverage
            chunk_result_asset_sr = chunk_asset_record["Result Asset"]
            chunk_asset_shifts = chunk_result_asset_sr.diff()
            if len(chunk_asset_shifts) > 0:
                chunk_asset_shifts.iloc[0] = 0
            lazy_chunk_result_asset = chunk_result_asset_sr.shift(periods=1)
            if len(lazy_chunk_result_asset) > 0:
                lazy_chunk_result_asset.iloc[0] = 1
            chunk_asset_changes_by_leverage = (
                1 + chunk_asset_shifts / lazy_chunk_result_asset * leverage
            )
            # fee
            chunk_fees = chunk_asset_record["Role"].copy()
            chunk_fees[chunk_fees == "maker"] = maker_fee
            chunk_fees[chunk_fees == "taker"] = taker_fee
            chunk_fees = chunk_fees.astype(np.float32)
            chunk_margin_ratios = chunk_asset_record["Margin Ratio"]
            chunk_asset_changes_by_fee = (
                1 - (chunk_fees / 100) * chunk_margin_ratios * leverage
            )
            # altogether
            chunk_asset_changes = (
                chunk_asset_changes_by_leverage * chunk_asset_changes_by_fee
            )
            chunk_asset_changes_list.append(chunk_asset_changes)

        unrealized_changes = unrealized_changes * leverage
        year_asset_changes: pd.Series = pd.concat(chunk_asset_changes_list)
        if not year_asset_changes.index.is_monotonic_increasing:
            year_asset_changes = await go(sort_pandas.series, year_asset_changes)

        if len(asset_record) > 0:
            start_point = asset_record.index[0]
            year_asset_changes[start_point] = float(1)
            if not year_asset_changes.index.is_monotonic_increasing:
                year_asset_changes = await go(sort_pandas.series, year_asset_changes)
        asset_record = asset_record.reindex(year_asset_changes.index)
        asset_record["Result Asset"] = year_asset_changes.cumprod()

        presentation_asset_record = asset_record.copy()
        presentation_unrealized_changes = unrealized_changes.copy()
        presentation_scribbles = scribbles.copy()
        presentation_account_state = account_state.copy()

        # ■■■■■ remember ■■■■■

        self.scribbles = presentation_scribbles
        self.account_state = presentation_account_state
        async with self.unrealized_changes.write_lock as cell:
            cell.data = presentation_unrealized_changes
        async with self.asset_record.write_lock as cell:
            cell.data = presentation_asset_record

        # ■■■■■ display ■■■■■

        asyncio.create_task(self.display_lines())
        asyncio.create_task(self.display_range_information())

        if self.about_viewing is None:
            text = "Nothing drawn"
            solie.window.label_19.setText(text)
        else:
            year = self.about_viewing["year"]
            strategy_code_name = self.about_viewing["strategy_code_name"]
            strategy_version = self.about_viewing["strategy_version"]
            text = ""
            text += f"Target year {year}"
            text += "  ⦁  "
            text += f"Strategy code name {strategy_code_name}"
            text += "  ⦁  "
            text += f"Strategy version {strategy_version}"
            solie.window.label_19.setText(text)

    async def display_year_range(self, *args, **kwargs):
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
        widget = solie.window.plot_widget_2
        widget.setXRange(range_start, range_end)

    async def delete_calculation_data(self, *args, **kwargs):
        year = self.calculation_settings["year"]
        strategy_index = self.calculation_settings["strategy_index"]

        strategy = solie.window.strategist.strategies[strategy_index]
        strategy_code_name = strategy["code_name"]
        strategy_version = strategy["version"]

        path_start = f"{self.workerpath}/{strategy_code_name}_{strategy_version}_{year}"
        asset_record_path = path_start + "_asset_record.pickle"
        unrealized_changes_path = path_start + "_unrealized_changes.pickle"
        scribbles_path = path_start + "_scribbles.pickle"
        account_state_path = path_start + "_account_state.pickle"
        virtual_state_path = path_start + "_virtual_state.pickle"

        does_file_exist = False

        if os.path.exists(asset_record_path):
            does_file_exist = True
        if os.path.exists(unrealized_changes_path):
            does_file_exist = True
        if os.path.exists(scribbles_path):
            does_file_exist = True
        if os.path.exists(account_state_path):
            does_file_exist = True
        if os.path.exists(virtual_state_path):
            does_file_exist = True

        if not does_file_exist:
            question = [
                "No calculation data on this combination",
                f"You should calculate first on year {year} with strategy code name"
                f" {strategy_code_name} version {strategy_version}.",
                ["Okay"],
            ]
            await solie.window.ask(question)
            return
        else:
            question = [
                "Are you sure you want to delete calculation data on this combination?",
                "If you do, you should perform the calculation again to see the"
                f" prediction on year {year} with strategy code name"
                f" {strategy_code_name} version {strategy_version}. Calculation data of"
                " other combinations does not get affected.",
                ["Cancel", "Delete"],
            ]
            answer = await solie.window.ask(question)
            if answer in (0, 1):
                return

        try:
            os.remove(asset_record_path)
        except FileNotFoundError:
            pass
        try:
            os.remove(unrealized_changes_path)
        except FileNotFoundError:
            pass
        try:
            os.remove(scribbles_path)
        except FileNotFoundError:
            pass
        try:
            os.remove(account_state_path)
        except FileNotFoundError:
            pass
        try:
            os.remove(virtual_state_path)
        except FileNotFoundError:
            pass

        await self.erase()

    async def draw(self, *args, **kwargs):
        year = self.calculation_settings["year"]
        strategy_index = self.calculation_settings["strategy_index"]

        strategy = solie.window.strategist.strategies[strategy_index]
        strategy_code_name = strategy["code_name"]
        strategy_version = strategy["version"]

        path_start = f"{self.workerpath}/{strategy_code_name}_{strategy_version}_{year}"
        asset_record_path = path_start + "_asset_record.pickle"
        unrealized_changes_path = path_start + "_unrealized_changes.pickle"
        scribbles_path = path_start + "_scribbles.pickle"
        account_state_path = path_start + "_account_state.pickle"

        try:
            async with self.raw_asset_record.write_lock as cell:
                new = await go(pd.read_pickle, asset_record_path)
                cell.data = new
            async with self.raw_unrealized_changes.write_lock as cell:
                new = await go(pd.read_pickle, unrealized_changes_path)
                cell.data = new
            async with aiofiles.open(scribbles_path, "rb") as file:
                content = await file.read()
                self.raw_scribbles = pickle.loads(content)
            async with aiofiles.open(account_state_path, "rb") as file:
                content = await file.read()
                self.raw_account_state = pickle.loads(content)
            self.about_viewing = {
                "year": year,
                "strategy_code_name": strategy_code_name,
                "strategy_version": strategy_version,
            }
            await self.present()
        except FileNotFoundError:
            question = [
                "No calculation data on this combination",
                f"You should calculate first on year {year} with strategy code name"
                f" {strategy_code_name} version {strategy_version}.",
                ["Okay"],
            ]
            await solie.window.ask(question)
            return

    async def match_graph_range(self, *args, **kwargs):
        range_start = solie.window.plot_widget.getAxis("bottom").range[0]
        range_end = solie.window.plot_widget.getAxis("bottom").range[1]
        widget = solie.window.plot_widget_2
        widget.setXRange(range_start, range_end, padding=0)  # type:ignore

    async def stop_calculation(self, *args, **kwargs):
        stop_flag.make("calculate_simulation")

    async def analyze_unrealized_peaks(self, *args, **kwargs):
        async with self.unrealized_changes.read_lock as cell:
            peak_indexes, _ = find_peaks(-cell.data, distance=3600 / 10)  # type:ignore
            peak_sr = cell.data.iloc[peak_indexes]
        peak_sr = peak_sr.sort_values().iloc[:12]
        if len(peak_sr) < 12:
            question = [
                "Calculation data is either missing or too short",
                "Cannot get the list of meaningful spots with lowest unrealized"
                " profit.",
                ["Okay"],
            ]
            await solie.window.ask(question)
        else:
            text_lines = [
                f"{index} {peak_value:+.2f}%"
                for index, peak_value in peak_sr.iteritems()
            ]
            question = [
                "Spots with lowest unrealized profit",
                "\n".join(text_lines),
                ["Okay"],
            ]
            await solie.window.ask(question)

    async def toggle_combined_draw(self, *args, **kwargs):
        is_checked = args[0]
        if is_checked:
            self.should_draw_all_years = True
        else:
            self.should_draw_all_years = False
        await self.display_lines()
