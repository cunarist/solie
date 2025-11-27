"""Simulation calculation orchestrator."""

import math
import pickle
from asyncio import gather, sleep
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

import aiofiles
import pandas as pd
from PySide6.QtWidgets import QProgressBar

from solie.common import UniqueTask, get_sync_manager, spawn, spawn_blocking
from solie.utility import (
    MAX_PREPARATION_STEPS,
    PROGRESS_BAR_MAX,
    AccountState,
    Cell,
    Strategy,
    VirtualPosition,
    VirtualState,
    create_empty_account_state,
    create_empty_asset_record,
    create_empty_unrealized_changes,
    sort_data_frame,
    sort_series,
)
from solie.widget import GraphLines

from .analyze_market import (
    CalculationInput,
    CalculationOutput,
    make_indicators,
    simulate_chunk,
)


class BlankStates(NamedTuple):
    """Blank initial states for calculation."""

    asset_record: pd.DataFrame
    unrealized_changes: pd.Series
    scribbles: dict[Any, Any]
    account_state: AccountState
    virtual_state: VirtualState


class PreviousState(NamedTuple):
    """Previous calculation state."""

    asset_record: pd.DataFrame
    unrealized_changes: pd.Series
    scribbles: dict[Any, Any]
    account_state: AccountState
    virtual_state: VirtualState
    calculate_from: datetime
    calculate_until: datetime


class WidgetReferences(NamedTuple):
    """References to UI widgets for progress display."""

    pre_progressbar: QProgressBar
    main_progressbar: QProgressBar
    simulation_graph: GraphLines


class CalculationConfig(NamedTuple):
    """Configuration for simulation calculation."""

    year: int
    strategy: Strategy
    target_symbols: list[str]
    only_visible: bool
    should_draw_all_years: bool


class CalculationResult(NamedTuple):
    """Result of simulation calculation."""

    asset_record: pd.DataFrame
    unrealized_changes: pd.Series
    scribbles: dict[Any, Any]
    account_state: AccountState


class SimulationCalculator:
    """Orchestrates simulation calculation for a specific year and strategy."""

    def __init__(
        self,
        *,
        unique_task: UniqueTask,
        config: CalculationConfig,
        workerpath: Path,
        year_candle_data: pd.DataFrame,
        widgets: WidgetReferences,
    ) -> None:
        """Initialize simulation calculator."""
        self.unique_task = unique_task
        self.config = config
        self.workerpath = workerpath
        self.year_candle_data = year_candle_data
        self.widgets = widgets

        # Convenience accessors
        self.year = config.year
        self.strategy = config.strategy
        self.target_symbols = config.target_symbols
        self.only_visible = config.only_visible
        self.should_draw_all_years = config.should_draw_all_years

        self.prepare_step = 0
        self.calculate_step = Cell(0)

        # File paths
        prefix = f"{self.strategy.code_name}_{self.strategy.version}_{self.year}"
        self.asset_record_path = workerpath / f"{prefix}_asset_record.pickle"
        self.unrealized_changes_path = (
            workerpath / f"{prefix}_unrealized_changes.pickle"
        )
        self.scribbles_path = workerpath / f"{prefix}_scribbles.pickle"
        self.account_state_path = workerpath / f"{prefix}_account_state.pickle"
        self.virtual_state_path = workerpath / f"{prefix}_virtual_state.pickle"

        # Time range
        self.slice_from = datetime(self.year, 1, 1, tzinfo=UTC)
        if self.year == datetime.now(UTC).year:
            self.slice_until = datetime.now(UTC)
            self.slice_until = self.slice_until.replace(
                minute=0,
                second=0,
                microsecond=0,
            )
        else:
            self.slice_until = datetime(self.year + 1, 1, 1, tzinfo=UTC)
        self.slice_until -= timedelta(seconds=1)

    async def calculate(self) -> CalculationResult:
        """Run the simulation calculation."""
        bar_task = spawn(self._play_progress_bar())
        bar_task.add_done_callback(lambda _: self.widgets.pre_progressbar.setValue(0))
        bar_task.add_done_callback(lambda _: self.widgets.main_progressbar.setValue(0))
        self.unique_task.add_done_callback(lambda _: bar_task.cancel())

        self.prepare_step = 1

        self.year_candle_data = self.year_candle_data.interpolate()

        self.prepare_step = 2

        blank_states = self._create_blank_states()

        self.prepare_step = 3

        previous_state = await self._load_or_create_previous_state(blank_states)

        self.prepare_step = 4

        should_calculate = (
            previous_state.calculate_from < previous_state.calculate_until
        )
        if len(previous_state.asset_record) == 0:
            previous_state.asset_record.loc[previous_state.calculate_from, "CAUSE"] = (
                "OTHER"
            )
            previous_state.asset_record.loc[
                previous_state.calculate_from,
                "RESULT_ASSET",
            ] = 1.0

        self.prepare_step = 5

        calculation_inputs = await self._create_calculation_inputs(
            should_calculate,
            previous_state,
            blank_states,
        )

        self.prepare_step = 6

        calculation_output_data = await self._run_calculation(
            should_calculate,
            calculation_inputs,
            previous_state,
        )

        self.calculate_step.value = 1000

        result = await self._merge_calculation_results(
            should_calculate,
            calculation_output_data,
            previous_state,
        )

        asset_record = result.asset_record
        unrealized_changes = result.unrealized_changes
        scribbles = result.scribbles
        account_state = result.account_state

        if not self.only_visible and should_calculate:
            await self._save_calculation_results(
                asset_record,
                unrealized_changes,
                scribbles,
                account_state,
            )

        return CalculationResult(
            asset_record=asset_record,
            unrealized_changes=unrealized_changes,
            scribbles=scribbles,
            account_state=account_state,
        )

    async def _play_progress_bar(self) -> None:
        """Animate progress bars."""
        while True:
            if (
                self.prepare_step == MAX_PREPARATION_STEPS
                and self.calculate_step.value == PROGRESS_BAR_MAX
            ):
                is_progressbar_filled = True
                progressbar_value = self.widgets.pre_progressbar.value()
                if progressbar_value < PROGRESS_BAR_MAX:
                    is_progressbar_filled = False
                progressbar_value = self.widgets.main_progressbar.value()
                if progressbar_value < PROGRESS_BAR_MAX:
                    is_progressbar_filled = False
                if is_progressbar_filled:
                    await sleep(0.1)
                    self.widgets.pre_progressbar.setValue(0)
                    self.widgets.main_progressbar.setValue(0)
                    return

            widget = self.widgets.pre_progressbar
            before_value = widget.value()
            if before_value < PROGRESS_BAR_MAX:
                remaining = (
                    math.ceil(
                        PROGRESS_BAR_MAX / MAX_PREPARATION_STEPS * self.prepare_step,
                    )
                    - before_value
                )
                new_value = before_value + math.ceil(remaining * 0.2)
                widget.setValue(new_value)

            widget = self.widgets.main_progressbar
            before_value = widget.value()
            if before_value < PROGRESS_BAR_MAX:
                remaining = self.calculate_step.value - before_value
                new_value = before_value + math.ceil(remaining * 0.2)
                widget.setValue(new_value)

            await sleep(0.01)

    def _create_blank_states(self) -> BlankStates:
        """Create blank initial states."""
        blank_asset_record = create_empty_asset_record()
        blank_unrealized_changes = create_empty_unrealized_changes()
        blank_scribbles: dict[Any, Any] = {}
        blank_account_state = create_empty_account_state(self.target_symbols)
        blank_virtual_state = VirtualState(
            available_balance=1,
            positions={},
            placements={},
        )
        for symbol in self.target_symbols:
            blank_virtual_state.positions[symbol] = VirtualPosition(
                amount=0.0,
                entry_price=0.0,
            )
            blank_virtual_state.placements[symbol] = {}

        return BlankStates(
            asset_record=blank_asset_record,
            unrealized_changes=blank_unrealized_changes,
            scribbles=blank_scribbles,
            account_state=blank_account_state,
            virtual_state=blank_virtual_state,
        )

    async def _load_or_create_previous_state(
        self,
        blank_states: BlankStates,
    ) -> PreviousState:
        """Load previous calculation state or create blank state."""
        if self.only_visible:
            previous_asset_record = blank_states.asset_record.copy()
            previous_unrealized_changes = blank_states.unrealized_changes.copy()
            previous_scribbles = blank_states.scribbles.copy()
            previous_account_state = blank_states.account_state.model_copy(deep=True)
            previous_virtual_state = blank_states.virtual_state.model_copy(deep=True)

            graph_widget = self.widgets.simulation_graph.price_widget
            view_range = graph_widget.getAxis("bottom").range
            view_start = datetime.fromtimestamp(view_range[0], tz=UTC)
            view_end = datetime.fromtimestamp(view_range[1], tz=UTC)

            if self.should_draw_all_years:
                calculate_from = view_start
                calculate_until = view_end
            else:
                calculate_from = max(view_start, self.slice_from)
                calculate_until = min(view_end, self.slice_until)

        else:
            try:
                previous_asset_record: pd.DataFrame = await spawn_blocking(
                    pd.read_pickle,
                    self.asset_record_path,
                )
                previous_unrealized_changes: pd.Series = await spawn_blocking(
                    pd.read_pickle,
                    self.unrealized_changes_path,
                )
                async with aiofiles.open(self.scribbles_path, "rb") as file:
                    content = await file.read()
                    previous_scribbles = pickle.loads(content)
                async with aiofiles.open(self.account_state_path, "rb") as file:
                    content = await file.read()
                    previous_account_state: AccountState = pickle.loads(content)
                async with aiofiles.open(self.virtual_state_path, "rb") as file:
                    content = await file.read()
                    previous_virtual_state: VirtualState = pickle.loads(content)

                calculate_from = previous_account_state.observed_until
                calculate_until = self.slice_until
            except FileNotFoundError:
                previous_asset_record = blank_states.asset_record.copy()
                previous_unrealized_changes = blank_states.unrealized_changes.copy()
                previous_scribbles = blank_states.scribbles.copy()
                previous_account_state = blank_states.account_state.model_copy(
                    deep=True,
                )
                previous_virtual_state = blank_states.virtual_state.model_copy(
                    deep=True,
                )

                calculate_from = self.slice_from
                calculate_until = self.slice_until

        return PreviousState(
            asset_record=previous_asset_record,
            unrealized_changes=previous_unrealized_changes,
            scribbles=previous_scribbles,
            account_state=previous_account_state,
            virtual_state=previous_virtual_state,
            calculate_from=calculate_from,
            calculate_until=calculate_until,
        )

    async def _create_calculation_inputs(
        self,
        should_calculate: bool,
        previous_state: PreviousState,
        blank_states: BlankStates,
    ) -> list[CalculationInput]:
        """Create calculation input chunks."""
        calculation_inputs: list[CalculationInput] = []

        if not should_calculate:
            return calculation_inputs

        sync_manager = get_sync_manager()

        calculate_from = previous_state.calculate_from
        calculate_until = previous_state.calculate_until

        provide_from = calculate_from - timedelta(days=28)
        year_indicators = await spawn_blocking(
            make_indicators,
            strategy=self.strategy,
            target_symbols=self.target_symbols,
            candle_data=self.year_candle_data[provide_from:calculate_until],
        )

        needed_candle_data = self.year_candle_data[calculate_from:calculate_until]
        needed_index: pd.DatetimeIndex = needed_candle_data.index  # type:ignore
        needed_indicators = year_indicators.reindex(needed_index)

        parallel_chunk_days = self.strategy.parallel_simulation_chunk_days

        if parallel_chunk_days is None:
            progress_list = sync_manager.list([0.0])
            calculation_input = CalculationInput(
                strategy=self.strategy,
                progress_list=progress_list,
                target_progress=0,
                target_symbols=self.target_symbols,
                calculation_index=needed_index,
                chunk_candle_data=needed_candle_data,
                chunk_indicators=needed_indicators,
                chunk_asset_record=previous_state.asset_record,
                chunk_unrealized_changes=previous_state.unrealized_changes,
                chunk_scribbles=previous_state.scribbles,
                chunk_account_state=previous_state.account_state,
                chunk_virtual_state=previous_state.virtual_state,
            )
            calculation_inputs.append(calculation_input)

        else:
            division = timedelta(days=parallel_chunk_days)
            chunk_candle_data_list = [
                chunk_candle_data
                for _, chunk_candle_data in needed_candle_data.groupby(
                    pd.Grouper(freq=division, origin="epoch"),  # type:ignore
                )
            ]

            chunk_count = len(chunk_candle_data_list)
            progress_list = sync_manager.list([0.0] * chunk_count)

            for turn, chunk_candle_data in enumerate(chunk_candle_data_list):
                chunk_index: pd.DatetimeIndex = chunk_candle_data.index  # type:ignore
                chunk_indicators = needed_indicators.reindex(chunk_index)
                chunk_asset_record = previous_state.asset_record.iloc[0:0]
                chunk_unrealized_changes = previous_state.unrealized_changes.iloc[0:0]
                first_timestamp = chunk_index[0].timestamp()
                division_seconds = parallel_chunk_days * 24 * 60 * 60
                if turn == 0 and first_timestamp % division_seconds != 0:
                    chunk_scribbles = previous_state.scribbles
                    chunk_account_state = previous_state.account_state
                    chunk_virtual_state = previous_state.virtual_state
                else:
                    chunk_scribbles = blank_states.scribbles
                    chunk_account_state = blank_states.account_state
                    chunk_virtual_state = blank_states.virtual_state

                calculation_input = CalculationInput(
                    strategy=self.strategy,
                    progress_list=progress_list,
                    target_progress=turn,
                    target_symbols=self.target_symbols,
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

        return calculation_inputs

    async def _run_calculation(
        self,
        should_calculate: bool,
        calculation_inputs: list[CalculationInput],
        previous_state: PreviousState,
    ) -> list[CalculationOutput]:
        """Execute the actual simulation calculation."""
        calculation_output_data: list[CalculationOutput] = []

        if not should_calculate:
            return calculation_output_data

        coroutines = [
            spawn_blocking(simulate_chunk, input_data)
            for input_data in calculation_inputs
        ]
        gathered = gather(*coroutines)

        calculate_from = previous_state.calculate_from
        calculate_until = previous_state.calculate_until
        total_seconds = (calculate_until - calculate_from).total_seconds()

        async def update_calculation_step() -> None:
            progress_list = calculation_inputs[0].progress_list
            while True:
                if gathered.done():
                    return
                total_progress = sum(progress_list)
                self.calculate_step.value = math.ceil(
                    total_progress * 1000 / total_seconds,
                )
                await sleep(0.01)

        step_task = spawn(update_calculation_step())
        self.unique_task.add_done_callback(lambda _: step_task.cancel())

        return await gathered

    async def _merge_calculation_results(
        self,
        should_calculate: bool,
        calculation_output_data: list[CalculationOutput],
        previous_state: PreviousState,
    ) -> CalculationResult:
        """Merge calculation results into final output."""
        if should_calculate:
            asset_record = previous_state.asset_record
            for chunk_ouput_data in calculation_output_data:
                chunk_asset_record = chunk_ouput_data.chunk_asset_record
                concat_data = [asset_record, chunk_asset_record]
                asset_record: pd.DataFrame = pd.concat(concat_data)
            mask = ~asset_record.index.duplicated()
            asset_record = asset_record[mask]
            if not asset_record.index.is_monotonic_increasing:
                asset_record = await spawn_blocking(sort_data_frame, asset_record)

            unrealized_changes = previous_state.unrealized_changes
            for chunk_ouput_data in calculation_output_data:
                chunk_unrealized_changes = chunk_ouput_data.chunk_unrealized_changes
                concat_data = [unrealized_changes, chunk_unrealized_changes]
                unrealized_changes: pd.Series = pd.concat(concat_data)
            mask = ~unrealized_changes.index.duplicated()
            unrealized_changes = unrealized_changes[mask]
            if not unrealized_changes.index.is_monotonic_increasing:
                unrealized_changes = await spawn_blocking(
                    sort_series,
                    unrealized_changes,
                )

            scribbles = calculation_output_data[-1].chunk_scribbles
            account_state = calculation_output_data[-1].chunk_account_state

        else:
            asset_record = previous_state.asset_record
            unrealized_changes = previous_state.unrealized_changes
            scribbles = previous_state.scribbles
            account_state = previous_state.account_state

        return CalculationResult(
            asset_record=asset_record,
            unrealized_changes=unrealized_changes,
            scribbles=scribbles,
            account_state=account_state,
        )

    async def _save_calculation_results(
        self,
        asset_record: pd.DataFrame,
        unrealized_changes: pd.Series,
        scribbles: dict[Any, Any],
        account_state: AccountState,
    ) -> None:
        """Save calculation results to disk."""
        await spawn_blocking(asset_record.to_pickle, self.asset_record_path)
        await spawn_blocking(unrealized_changes.to_pickle, self.unrealized_changes_path)
        async with aiofiles.open(self.scribbles_path, "wb") as file:
            content = pickle.dumps(scribbles)
            await file.write(content)
        async with aiofiles.open(self.account_state_path, "wb") as file:
            content = pickle.dumps(account_state)
            await file.write(content)
        # Note: virtual_state is not saved in the original implementation
