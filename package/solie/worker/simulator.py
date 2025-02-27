import math
import pickle
from asyncio import gather, sleep
from datetime import datetime, timedelta, timezone
from typing import Any

import aiofiles
import aiofiles.os
import numpy as np
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6.QtWidgets import QMenu
from scipy.signal import find_peaks

from solie.common import UniqueTask, get_sync_manager, outsource, spawn, spawn_blocking
from solie.utility import (
    AccountState,
    CalculationInput,
    DurationRecorder,
    PositionDirection,
    RWLock,
    SimulationSettings,
    SimulationSummary,
    VirtualPosition,
    VirtualState,
    create_empty_account_state,
    create_empty_asset_record,
    create_empty_unrealized_changes,
    make_indicators,
    simulate_chunk,
    sort_data_frame,
    sort_series,
    to_moment,
)
from solie.widget import ask
from solie.window import Window

from .united import team


class Simulator:
    def __init__(self, window: Window, scheduler: AsyncIOScheduler):
        # ■■■■■ for data management ■■■■■

        self.window = window
        self.scheduler = scheduler
        self.workerpath = window.datapath / "simulator"

        # ■■■■■ internal memory ■■■■■

        self.line_display_task = UniqueTask()
        self.range_display_task = UniqueTask()
        self.calculation_task = UniqueTask()

        # ■■■■■ remember and display ■■■■■

        self.viewing_symbol = window.data_settings.target_symbols[0]
        self.should_draw_all_years = False

        self.simulation_settings = SimulationSettings(
            year=datetime.now(timezone.utc).year,
        )
        self.simulation_summary: SimulationSummary | None = None

        self.raw_account_state = create_empty_account_state(
            self.window.data_settings.target_symbols
        )
        self.raw_scribbles: dict[Any, Any] = {}
        self.raw_asset_record = RWLock(create_empty_asset_record())
        self.raw_unrealized_changes = RWLock(create_empty_unrealized_changes())

        self.account_state = create_empty_account_state(
            self.window.data_settings.target_symbols
        )
        self.scribbles: dict[Any, Any] = {}
        self.asset_record = RWLock(create_empty_asset_record())
        self.unrealized_changes = RWLock(create_empty_unrealized_changes())

        # ■■■■■ repetitive schedules ■■■■■

        self.scheduler.add_job(
            self.display_available_years,
            trigger="cron",
            hour="*",
        )
        self.scheduler.add_job(
            self.display_lines,
            trigger="cron",
            hour="*",
            kwargs={"periodic": True},
        )

        # ■■■■■ websocket streamings ■■■■■

        # ■■■■■ invoked by the internet connection status change ■■■■■

        # ■■■■■ connect UI events ■■■■■

        job = self.display_range_information
        outsource(window.simulation_graph.price_widget.sigRangeChanged, job)
        job = self.set_minimum_view_range
        outsource(window.simulation_graph.price_widget.sigRangeChanged, job)
        job = self.update_calculation_settings
        outsource(window.comboBox.currentIndexChanged, job)
        job = self.calculate
        outsource(window.pushButton_3.clicked, job)
        job = self.update_presentation_settings
        outsource(window.spinBox_2.editingFinished, job)
        job = self.update_presentation_settings
        outsource(window.doubleSpinBox.editingFinished, job)
        job = self.update_presentation_settings
        outsource(window.doubleSpinBox_2.editingFinished, job)
        job = self.erase
        outsource(window.pushButton_4.clicked, job)
        job = self.update_calculation_settings
        outsource(window.comboBox_5.currentIndexChanged, job)
        job = self.toggle_combined_draw
        outsource(window.checkBox_3.toggled, job)
        job = self.display_year_range
        outsource(window.pushButton_15.clicked, job)
        job = self.delete_calculation_data
        outsource(window.pushButton_16.clicked, job)
        job = self.draw
        outsource(window.pushButton_17.clicked, job)
        job = self.update_viewing_symbol
        outsource(window.comboBox_6.currentIndexChanged, job)

        action_menu = QMenu(self.window)
        self.window.pushButton_11.setMenu(action_menu)

        text = "Calculate temporarily only on visible range"
        job = self.simulate_only_visible
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Stop calculation"
        job = self.stop_calculation
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Find spots with lowest unrealized profit"
        job = self.analyze_unrealized_peaks
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Display same range as transaction graph"
        job = self.match_graph_range
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)

    async def load(self):
        await aiofiles.os.makedirs(self.workerpath, exist_ok=True)

        text = "Nothing drawn"
        self.window.label_19.setText(text)

    async def update_viewing_symbol(self):
        alias = self.window.comboBox_6.currentText()
        symbol = self.window.alias_to_symbol[alias]
        self.viewing_symbol = symbol

        await self.display_lines()

    async def update_calculation_settings(self):
        text = self.window.comboBox_5.currentText()
        if text == "":
            return
        from_year = self.simulation_settings.year
        to_year = int(text)
        self.simulation_settings.year = to_year
        if from_year != to_year:
            spawn(self.display_year_range())

        index = self.window.comboBox.currentIndex()
        self.simulation_settings.strategy_index = index

        await self.display_lines()

    async def update_presentation_settings(self):
        input_value = self.window.spinBox_2.value()
        self.simulation_settings.leverage = input_value
        input_value = self.window.doubleSpinBox.value()
        self.simulation_settings.taker_fee = input_value
        input_value = self.window.doubleSpinBox_2.value()
        self.simulation_settings.maker_fee = input_value
        await self.present()

    async def display_lines(self, periodic=False):
        self.line_display_task.spawn(self._display_lines(periodic))

    async def _display_lines(self, periodic: bool):
        # ■■■■■ get basic information ■■■■■

        symbol = self.viewing_symbol
        strategy_index = self.simulation_settings.strategy_index
        strategy = team.strategist.strategies[strategy_index]

        should_draw_all_years = self.should_draw_all_years

        # ■■■■■ ensure that the latest data was added ■■■■■

        async with team.collector.candle_data.read_lock as cell:
            if len(cell.data) == 0:
                return

        current_moment = to_moment(datetime.now(timezone.utc))
        before_moment = current_moment - timedelta(seconds=10)

        if periodic:
            for _ in range(50):
                async with team.collector.candle_data.read_lock as cell:
                    last_index = cell.data.index[-1]
                    if last_index == before_moment:
                        break
                await sleep(0.1)

        # ■■■■■ get ready for task duration measurement ■■■■■

        duration_recorder = DurationRecorder("DISPLAY_SIMULATION_LINES")

        # ■■■■■ set the slicing range ■■■■■

        if should_draw_all_years:
            years = await team.collector.check_saved_years()
            slice_from = datetime.fromtimestamp(0, tz=timezone.utc)
            slice_until = datetime.now(timezone.utc)
            slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
        else:
            year = self.simulation_settings.year
            years = [year]
            slice_from = datetime(year, 1, 1, tzinfo=timezone.utc)
            if year == datetime.now(timezone.utc).year:
                slice_until = datetime.now(timezone.utc)
                slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
            else:
                slice_until = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        slice_until -= timedelta(seconds=1)

        # ■■■■■ draw light lines ■■■■■

        position = self.account_state.positions[symbol]
        if position.direction == PositionDirection.NONE:
            entry_price = None
        else:
            entry_price = position.entry_price

        await self.window.simulation_graph.update_light_lines(
            mark_prices=[],
            aggregate_trades=[],
            book_tickers=[],
            entry_price=entry_price,
            observed_until=self.account_state.observed_until,
        )

        # ■■■■■ draw heavy lines ■■■■■

        divided_datas: list[pd.DataFrame] = []
        for year in years:
            more_df = await team.collector.read_saved_candle_data(year)
            divided_datas.append(more_df)
        candle_data_original = await spawn_blocking(pd.concat, divided_datas)
        if not candle_data_original.index.is_monotonic_increasing:
            candle_data_original = await spawn_blocking(
                sort_data_frame, candle_data_original
            )
        async with self.unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data.copy()
        async with self.asset_record.read_lock as cell:
            if len(cell.data) > 0:
                last_asset = cell.data.iloc[-1]["RESULT_ASSET"]
            else:
                last_asset = None
            before_record = cell.data[:slice_from]
            if len(before_record) > 0:
                before_asset = before_record.iloc[-1]["RESULT_ASSET"]
            else:
                before_asset = None
            asset_record = cell.data[slice_from:].copy()

        candle_data = candle_data_original[slice_from:]

        # add the right end
        if len(candle_data) > 0:
            last_written_moment = candle_data.index[-1]
            new_moment = last_written_moment + timedelta(seconds=10)
            new_index = candle_data.index.union([new_moment])
            candle_data = candle_data.reindex(new_index)

        if last_asset is not None:
            observed_until = self.account_state.observed_until
            if len(asset_record) == 0 or asset_record.index[-1] < observed_until:
                if slice_from < observed_until:
                    asset_record.loc[observed_until, "CAUSE"] = "OTHER"
                    asset_record.loc[observed_until, "RESULT_ASSET"] = last_asset
                    if not asset_record.index.is_monotonic_increasing:
                        asset_record = await spawn_blocking(
                            sort_data_frame, asset_record
                        )

        # add the left end
        if before_asset is not None:
            asset_record.loc[slice_from, "CAUSE"] = "OTHER"
            asset_record.loc[slice_from, "RESULT_ASSET"] = before_asset
            if not asset_record.index.is_monotonic_increasing:
                asset_record = await spawn_blocking(sort_data_frame, asset_record)

        await self.window.simulation_graph.update_heavy_lines(
            symbol=symbol,
            candle_data=candle_data,
            asset_record=asset_record,
            unrealized_changes=unrealized_changes,
        )

        # ■■■■■ draw custom lines ■■■■■

        indicators = await spawn_blocking(
            make_indicators,
            strategy=strategy,
            target_symbols=[self.viewing_symbol],
            candle_data=candle_data_original,
        )

        indicators = indicators[slice_from:slice_until]

        await self.window.simulation_graph.update_custom_lines(symbol, indicators)

        # ■■■■■ record task duration ■■■■■

        duration_recorder.record()

        # ■■■■■ set minimum view range ■■■■■

        await self.set_minimum_view_range()

    async def erase(self):
        self.raw_account_state = create_empty_account_state(
            self.window.data_settings.target_symbols
        )
        self.raw_scribbles = {}
        self.raw_asset_record = RWLock(create_empty_asset_record())
        self.raw_unrealized_changes = RWLock(create_empty_unrealized_changes())
        self.simulation_summary = None

        await self.present()

    async def display_available_years(self):
        years = await team.collector.check_saved_years()
        years.sort(reverse=True)

        widget = self.window.comboBox_5
        choices = [int(widget.itemText(i)) for i in range(widget.count())]
        choices.sort(reverse=True)

        if years != choices:
            # if it's changed
            self.window.comboBox_5.clear()
            self.window.comboBox_5.addItems([str(y) for y in years])

    async def simulate_only_visible(self):
        await self.calculate(only_visible=True)

    async def display_range_information(self):
        self.range_display_task.spawn(self._display_range_information())

    async def _display_range_information(self):
        symbol = self.viewing_symbol
        price_widget = self.window.simulation_graph.price_widget

        range_start_timestamp = price_widget.getAxis("bottom").range[0]
        range_start_timestamp = max(range_start_timestamp, 0.0)
        range_start = datetime.fromtimestamp(range_start_timestamp, tz=timezone.utc)

        range_end_timestamp = price_widget.getAxis("bottom").range[1]
        if range_end_timestamp < 0:
            # case when pyqtgraph passed negative value because it's too big
            range_end_timestamp = 9223339636
        else:
            # maximum value available in pandas
            range_end_timestamp = min(range_end_timestamp, 9223339636.0)
        range_end = datetime.fromtimestamp(range_end_timestamp, tz=timezone.utc)

        range_length = range_end - range_start
        range_days = range_length.days
        range_hours, remains = divmod(range_length.seconds, 3600)
        range_minutes, remains = divmod(remains, 60)

        async with self.unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data[range_start:range_end].copy()
        async with self.asset_record.read_lock as cell:
            asset_record = cell.data[range_start:range_end].copy()

        auto_trade_mask = asset_record["CAUSE"] == "AUTO_TRADE"
        asset_changes = asset_record["RESULT_ASSET"].pct_change(fill_method=None) + 1  # type:ignore
        asset_record = asset_record[auto_trade_mask]
        asset_changes = asset_changes.reindex(asset_record.index, fill_value=1.0)
        symbol_mask = asset_record["SYMBOL"] == symbol

        # trade count
        total_change_count = len(asset_changes)
        symbol_change_count = len(asset_changes[symbol_mask])
        # trade volume
        if len(asset_record) > 0:
            total_margin_ratio = asset_record["MARGIN_RATIO"].sum()
        else:
            total_margin_ratio = 0
        if len(asset_record[symbol_mask]) > 0:
            symbol_margin_ratio = asset_record[symbol_mask]["MARGIN_RATIO"].sum()
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
            min_unrealized_change = 0.0

        view_range = price_widget.getAxis("left").range
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
        text += f" *{symbol_margin_ratio:.4f}({total_margin_ratio:.4f})"
        text += "  ⦁  "
        text += f"Total realized profit {symbol_yield:+.4f}({total_yield:+.4f})%"
        text += "  ⦁  "
        text += "Lowest unrealized profit"
        text += f" {min_unrealized_change * 100:+.4f}%"
        self.window.label_13.setText(text)

    async def set_minimum_view_range(self):
        widget = self.window.simulation_graph.price_widget
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore
        widget = self.window.simulation_graph.asset_widget
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore

    async def calculate(self, only_visible=False):
        self.calculation_task.spawn(self._calculate(only_visible))

    async def _calculate(self, only_visible: bool):
        unique_task = self.calculation_task
        prepare_step = 0
        calculate_step = 0

        async def play_progress_bar():
            while True:
                if prepare_step == 6 and calculate_step == 1000:
                    is_progressbar_filled = True
                    progressbar_value = self.window.progressBar_4.value()
                    if progressbar_value < 1000:
                        is_progressbar_filled = False
                    progressbar_value = self.window.progressBar.value()
                    if progressbar_value < 1000:
                        is_progressbar_filled = False
                    if is_progressbar_filled:
                        await sleep(0.1)
                        self.window.progressBar_4.setValue(0)
                        self.window.progressBar.setValue(0)
                        return
                widget = self.window.progressBar_4
                before_value = widget.value()
                if before_value < 1000:
                    remaining = math.ceil(1000 / 6 * prepare_step) - before_value
                    new_value = before_value + math.ceil(remaining * 0.2)
                    widget.setValue(new_value)
                widget = self.window.progressBar
                before_value = widget.value()
                if before_value < 1000:
                    remaining = calculate_step - before_value
                    new_value = before_value + math.ceil(remaining * 0.2)
                    widget.setValue(new_value)
                await sleep(0.01)

        bar_task = spawn(play_progress_bar())
        bar_task.add_done_callback(lambda _: self.window.progressBar_4.setValue(0))
        bar_task.add_done_callback(lambda _: self.window.progressBar.setValue(0))
        unique_task.add_done_callback(lambda _: bar_task.cancel())

        prepare_step = 1

        # ■■■■■ default values and the strategy ■■■■■

        year = self.simulation_settings.year
        strategy_index = self.simulation_settings.strategy_index

        strategy = team.strategist.strategies[strategy_index]
        strategy_code_name = strategy.code_name
        strategy_version = strategy.version
        should_parallelize = strategy.parallelized_simulation
        chunk_length = strategy.chunk_division

        workerpath = self.workerpath
        prefix = f"{strategy_code_name}_{strategy_version}_{year}"
        asset_record_path = workerpath / f"{prefix}_asset_record.pickle"
        unrealized_changes_path = workerpath / f"{prefix}_unrealized_changes.pickle"
        scribbles_path = workerpath / f"{prefix}_scribbles.pickle"
        account_state_path = workerpath / f"{prefix}_account_state.pickle"
        virtual_state_path = workerpath / f"{prefix}_virtual_state.pickle"

        target_symbols = self.window.data_settings.target_symbols

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
        year_candle_data = await team.collector.read_saved_candle_data(year)

        # Interpolate so that there's no inappropriate holes.
        year_candle_data = year_candle_data.interpolate()

        prepare_step = 3

        # ■■■■■ prepare data and calculation range ■■■■■

        blank_asset_record = create_empty_asset_record()
        blank_unrealized_changes = create_empty_unrealized_changes()
        blank_scribbles = {}
        blank_account_state = create_empty_account_state(
            self.window.data_settings.target_symbols
        )
        blank_virtual_state = VirtualState(
            available_balance=1,
            positions={},
            placements={},
        )
        for symbol in target_symbols:
            blank_virtual_state.positions[symbol] = VirtualPosition(
                amount=0.0,
                entry_price=0.0,
            )
            blank_virtual_state.placements[symbol] = {}

        prepare_step = 4

        if only_visible:
            # when calculating only on visible range

            previous_asset_record = blank_asset_record.copy()
            previous_unrealized_changes = blank_unrealized_changes.copy()
            previous_scribbles = blank_scribbles.copy()
            previous_account_state = blank_account_state.model_copy(deep=True)
            previous_virtual_state = blank_virtual_state.model_copy(deep=True)

            graph_widget = self.window.simulation_graph.price_widget
            view_range = graph_widget.getAxis("bottom").range
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
                previous_asset_record: pd.DataFrame = await spawn_blocking(
                    pd.read_pickle,
                    asset_record_path,
                )
                previous_unrealized_changes: pd.Series = await spawn_blocking(
                    pd.read_pickle,
                    unrealized_changes_path,
                )
                async with aiofiles.open(scribbles_path, "rb") as file:
                    content = await file.read()
                    previous_scribbles = pickle.loads(content)
                async with aiofiles.open(account_state_path, "rb") as file:
                    content = await file.read()
                    previous_account_state: AccountState = pickle.loads(content)
                async with aiofiles.open(virtual_state_path, "rb") as file:
                    content = await file.read()
                    previous_virtual_state: VirtualState = pickle.loads(content)

                calculate_from = previous_account_state.observed_until
                calculate_until = slice_until
            except FileNotFoundError:
                previous_asset_record = blank_asset_record.copy()
                previous_unrealized_changes = blank_unrealized_changes.copy()
                previous_scribbles = blank_scribbles.copy()
                previous_account_state = blank_account_state.model_copy(deep=True)
                previous_virtual_state = blank_virtual_state.model_copy(deep=True)

                calculate_from = slice_from
                calculate_until = slice_until

        should_calculate = calculate_from < calculate_until
        if len(previous_asset_record) == 0:
            previous_asset_record.loc[calculate_from, "CAUSE"] = "OTHER"
            previous_asset_record.loc[calculate_from, "RESULT_ASSET"] = 1.0

        prepare_step = 5

        # ■■■■■ prepare per chunk data ■■■■■

        sync_manager = get_sync_manager()

        calculation_inputs: list[CalculationInput] = []
        progress_list = sync_manager.list([0])

        if should_calculate:
            # a little more data for generation
            provide_from = calculate_from - timedelta(days=28)
            year_indicators = await spawn_blocking(
                make_indicators,
                strategy=strategy,
                target_symbols=target_symbols,
                candle_data=year_candle_data[provide_from:calculate_until],
            )

            # range cut
            needed_candle_data = year_candle_data[calculate_from:calculate_until]
            needed_index: pd.DatetimeIndex = needed_candle_data.index  # type:ignore
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
                progress_list = sync_manager.list([0] * chunk_count)

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

                    calculation_input = CalculationInput(
                        strategy=strategy,
                        progress_list=progress_list,
                        target_progress=turn,
                        target_symbols=target_symbols,
                        calculation_index=chunk_index,
                        chunk_candle_data=chunk_candle_data,
                        chunk_indicators=chunk_indicators,
                        chunk_asset_record=chunk_asset_record,
                        chunk_unrealized_changes=chunk_unrealized_changes,
                        chunk_scribbles=chunk_scribbles,
                        chunk_account_state=chunk_account_state,
                        chunk_virtual_state=chunk_virtual_state,
                    )
                    calculation_inputs.append(calculation_input)

            else:
                calculation_input = CalculationInput(
                    strategy=strategy,
                    progress_list=progress_list,
                    target_progress=0,
                    target_symbols=target_symbols,
                    calculation_index=needed_index,
                    chunk_candle_data=needed_candle_data,
                    chunk_indicators=needed_indicators,
                    chunk_asset_record=previous_asset_record,
                    chunk_unrealized_changes=previous_unrealized_changes,
                    chunk_scribbles=previous_scribbles,
                    chunk_account_state=previous_account_state,
                    chunk_virtual_state=previous_virtual_state,
                )
                calculation_inputs.append(calculation_input)

        prepare_step = 6

        # ■■■■■ calculate ■■■■■

        calculation_output_data = []

        if should_calculate:
            coroutines = [
                spawn_blocking(simulate_chunk, input_data)
                for input_data in calculation_inputs
            ]
            gathered = gather(*coroutines)

            total_seconds = (calculate_until - calculate_from).total_seconds()

            async def update_calculation_step():
                nonlocal calculate_step
                while True:
                    if gathered.done():
                        return
                    total_progress = sum(progress_list)
                    calculate_step = math.ceil(total_progress * 1000 / total_seconds)
                    await sleep(0.01)

            step_task = spawn(update_calculation_step())
            unique_task.add_done_callback(lambda _: step_task.cancel())

            calculation_output_data = await gathered

        calculate_step = 1000

        # ■■■■■ get calculation result ■■■■■

        if should_calculate:
            asset_record = previous_asset_record
            for chunk_ouput_data in calculation_output_data:
                chunk_asset_record = chunk_ouput_data.chunk_asset_record
                concat_data = [asset_record, chunk_asset_record]
                asset_record: pd.DataFrame = pd.concat(concat_data)
            mask = ~asset_record.index.duplicated()
            asset_record = asset_record[mask]
            if not asset_record.index.is_monotonic_increasing:
                asset_record = await spawn_blocking(sort_data_frame, asset_record)

            unrealized_changes = previous_unrealized_changes
            for chunk_ouput_data in calculation_output_data:
                chunk_unrealized_changes = chunk_ouput_data.chunk_unrealized_changes
                concat_data = [unrealized_changes, chunk_unrealized_changes]
                unrealized_changes: pd.Series = pd.concat(concat_data)
            mask = ~unrealized_changes.index.duplicated()
            unrealized_changes = unrealized_changes[mask]
            if not unrealized_changes.index.is_monotonic_increasing:
                unrealized_changes = await spawn_blocking(
                    sort_series, unrealized_changes
                )

            scribbles = calculation_output_data[-1].chunk_scribbles
            account_state = calculation_output_data[-1].chunk_account_state
            virtual_state = calculation_output_data[-1].chunk_virtual_state

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
        self.simulation_summary = SimulationSummary(
            year=year,
            strategy_code_name=strategy_code_name,
            strategy_version=strategy_version,
        )
        await self.present()

        # ■■■■■ save if properly calculated ■■■■■

        if not only_visible and should_calculate:
            await spawn_blocking(asset_record.to_pickle, asset_record_path)
            await spawn_blocking(unrealized_changes.to_pickle, unrealized_changes_path)
            async with aiofiles.open(scribbles_path, "wb") as file:
                content = pickle.dumps(scribbles)
                await file.write(content)
            async with aiofiles.open(account_state_path, "wb") as file:
                content = pickle.dumps(account_state)
                await file.write(content)
            async with aiofiles.open(virtual_state_path, "wb") as file:
                content = pickle.dumps(virtual_state)
                await file.write(content)

    async def present(self):
        maker_fee = self.simulation_settings.maker_fee
        taker_fee = self.simulation_settings.taker_fee
        leverage = self.simulation_settings.leverage

        async with self.raw_asset_record.read_lock as cell:
            asset_record = cell.data.copy()

        async with self.raw_unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data.copy()

        scribbles = self.raw_scribbles.copy()
        account_state = self.raw_account_state.model_copy(deep=True)

        # ■■■■■ get strategy details ■■■■

        if self.simulation_summary is None:
            should_parallelize = False
            chunk_length = 0
        else:
            strategy_index = self.simulation_settings.strategy_index
            strategy = team.strategist.strategies[strategy_index]
            should_parallelize = strategy.parallelized_simulation
            chunk_length = strategy.chunk_division

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

        chunk_asset_changes_list: list[pd.Series] = []
        for turn in range(chunk_count):
            chunk_asset_record = chunk_asset_record_list[turn]
            # leverage
            chunk_result_asset_sr = chunk_asset_record["RESULT_ASSET"]
            chunk_asset_shifts: pd.Series = chunk_result_asset_sr.diff()
            if len(chunk_asset_shifts) > 0:
                chunk_asset_shifts.iloc[0] = 0.0
            lazy_chunk_result_asset = chunk_result_asset_sr.shift(periods=1)
            if len(lazy_chunk_result_asset) > 0:
                lazy_chunk_result_asset.iloc[0] = 1
            chunk_asset_changes_by_leverage = (
                1 + chunk_asset_shifts / lazy_chunk_result_asset * leverage
            )
            # fee
            chunk_fees = chunk_asset_record["ROLE"].copy()
            chunk_fees[chunk_fees == "MAKER"] = maker_fee
            chunk_fees[chunk_fees == "TAKER"] = taker_fee
            chunk_fees = chunk_fees.astype(np.float32)
            chunk_margin_ratios = chunk_asset_record["MARGIN_RATIO"]
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
            year_asset_changes = await spawn_blocking(sort_series, year_asset_changes)

        if len(asset_record) > 0:
            start_point = asset_record.index[0]
            year_asset_changes[start_point] = 1.0
            if not year_asset_changes.index.is_monotonic_increasing:
                year_asset_changes = await spawn_blocking(
                    sort_series, year_asset_changes
                )
        asset_record = asset_record.reindex(year_asset_changes.index)
        asset_record["RESULT_ASSET"] = year_asset_changes.cumprod()

        presentation_asset_record = asset_record.copy()
        presentation_unrealized_changes = unrealized_changes.copy()
        presentation_scribbles = scribbles.copy()
        presentation_account_state = account_state.model_copy(deep=True)

        # ■■■■■ remember ■■■■■

        self.scribbles = presentation_scribbles
        self.account_state = presentation_account_state
        async with self.unrealized_changes.write_lock as cell:
            cell.data = presentation_unrealized_changes
        async with self.asset_record.write_lock as cell:
            cell.data = presentation_asset_record

        # ■■■■■ display ■■■■■

        spawn(self.display_lines())
        spawn(self.display_range_information())

        if self.simulation_summary is None:
            text = "Nothing drawn"
            self.window.label_19.setText(text)
        else:
            year = self.simulation_summary.year
            strategy_code_name = self.simulation_summary.strategy_code_name
            strategy_version = self.simulation_summary.strategy_version
            text = ""
            text += f"Target year {year}"
            text += "  ⦁  "
            text += f"Strategy code name {strategy_code_name}"
            text += "  ⦁  "
            text += f"Strategy version {strategy_version}"
            self.window.label_19.setText(text)

    async def display_year_range(self):
        range_start = datetime(
            year=self.simulation_settings.year,
            month=1,
            day=1,
            tzinfo=timezone.utc,
        )
        range_start = range_start.timestamp()
        range_end = datetime(
            year=self.simulation_settings.year + 1,
            month=1,
            day=1,
            tzinfo=timezone.utc,
        )
        range_end = range_end.timestamp()
        widget = self.window.simulation_graph.price_widget
        widget.setXRange(range_start, range_end)

    async def delete_calculation_data(self):
        year = self.simulation_settings.year
        strategy_index = self.simulation_settings.strategy_index

        strategy = team.strategist.strategies[strategy_index]
        strategy_code_name = strategy.code_name
        strategy_version = strategy.version

        workerpath = self.workerpath
        prefix = f"{strategy_code_name}_{strategy_version}_{year}"
        asset_record_path = workerpath / f"{prefix}_asset_record.pickle"
        unrealized_changes_path = workerpath / f"{prefix}_unrealized_changes.pickle"
        scribbles_path = workerpath / f"{prefix}_scribbles.pickle"
        account_state_path = workerpath / f"{prefix}_account_state.pickle"
        virtual_state_path = workerpath / f"{prefix}_virtual_state.pickle"

        does_file_exist = False

        if await aiofiles.os.path.isfile(asset_record_path):
            does_file_exist = True
        if await aiofiles.os.path.isfile(unrealized_changes_path):
            does_file_exist = True
        if await aiofiles.os.path.isfile(scribbles_path):
            does_file_exist = True
        if await aiofiles.os.path.isfile(account_state_path):
            does_file_exist = True
        if await aiofiles.os.path.isfile(virtual_state_path):
            does_file_exist = True

        if not does_file_exist:
            await ask(
                "No calculation data on this combination",
                f"You should calculate first on year {year} with strategy code name"
                f" {strategy_code_name} version {strategy_version}.",
                ["Okay"],
            )
            return
        else:
            answer = await ask(
                "Are you sure you want to delete calculation data on this combination?",
                "If you do, you should perform the calculation again to see the"
                f" prediction on year {year} with strategy code name"
                f" {strategy_code_name} version {strategy_version}. Calculation data of"
                " other combinations does not get affected.",
                ["Cancel", "Delete"],
            )
            if answer in (0, 1):
                return

        if await aiofiles.os.path.isfile(asset_record_path):
            await aiofiles.os.remove(asset_record_path)
        if await aiofiles.os.path.isfile(unrealized_changes_path):
            await aiofiles.os.remove(unrealized_changes_path)
        if await aiofiles.os.path.isfile(scribbles_path):
            await aiofiles.os.remove(scribbles_path)
        if await aiofiles.os.path.isfile(account_state_path):
            await aiofiles.os.remove(account_state_path)
        if await aiofiles.os.path.isfile(virtual_state_path):
            await aiofiles.os.remove(virtual_state_path)

        await self.erase()

    async def draw(self):
        year = self.simulation_settings.year
        strategy_index = self.simulation_settings.strategy_index

        strategy = team.strategist.strategies[strategy_index]
        strategy_code_name = strategy.code_name
        strategy_version = strategy.version

        workerpath = self.workerpath
        prefix = f"{strategy_code_name}_{strategy_version}_{year}"
        asset_record_path = workerpath / f"{prefix}_asset_record.pickle"
        unrealized_changes_path = workerpath / f"{prefix}_unrealized_changes.pickle"
        scribbles_path = workerpath / f"{prefix}_scribbles.pickle"
        account_state_path = workerpath / f"{prefix}_account_state.pickle"

        try:
            async with self.raw_asset_record.write_lock as cell:
                new = await spawn_blocking(pd.read_pickle, asset_record_path)
                cell.data = new
            async with self.raw_unrealized_changes.write_lock as cell:
                new = await spawn_blocking(pd.read_pickle, unrealized_changes_path)
                cell.data = new
            async with aiofiles.open(scribbles_path, "rb") as file:
                content = await file.read()
                self.raw_scribbles = pickle.loads(content)
            async with aiofiles.open(account_state_path, "rb") as file:
                content = await file.read()
                self.raw_account_state: AccountState = pickle.loads(content)
            self.simulation_summary = SimulationSummary(
                year=year,
                strategy_code_name=strategy_code_name,
                strategy_version=strategy_version,
            )
            await self.present()
        except FileNotFoundError:
            await ask(
                "No calculation data on this combination",
                f"You should calculate first on year {year} with strategy code name"
                f" {strategy_code_name} version {strategy_version}.",
                ["Okay"],
            )
            return

    async def match_graph_range(self):
        graph_from = self.window.transaction_graph.price_widget
        graph_to = self.window.simulation_graph.price_widget
        graph_range = graph_from.getAxis("bottom").range
        range_start = graph_range[0]
        range_end = graph_range[1]
        graph_to.setXRange(range_start, range_end, padding=0)  # type:ignore

    async def stop_calculation(self):
        if self.calculation_task is not None:
            self.calculation_task.cancel()

    async def analyze_unrealized_peaks(self):
        async with self.unrealized_changes.read_lock as cell:
            peak_indexes, _ = find_peaks(-cell.data, distance=3600 / 10)
            peak_sr = cell.data.iloc[peak_indexes]
        peak_sr = peak_sr.sort_values().iloc[:12]
        if len(peak_sr) < 12:
            await ask(
                "Calculation data is either missing or too short",
                "Cannot get the list of meaningful spots with lowest unrealized"
                " profit.",
                ["Okay"],
            )
        else:
            text_lines = [
                f"{index} {peak_value:+.2f}%"
                for index, peak_value in peak_sr.iteritems()
            ]
            await ask(
                "Spots with lowest unrealized profit",
                "\n".join(text_lines),
                ["Okay"],
            )

    async def toggle_combined_draw(self):
        is_checked = self.window.checkBox_3.isChecked()
        if is_checked:
            self.should_draw_all_years = True
        else:
            self.should_draw_all_years = False
        await self.display_lines()
