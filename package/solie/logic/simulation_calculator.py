"""Simulation calculation orchestrator."""

from __future__ import annotations

import math
import sqlite3
from asyncio import sleep
from collections import deque
from collections.abc import Generator
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from multiprocessing.managers import ListProxy
from numbers import Real
from pathlib import Path
from sqlite3 import Connection
from typing import Any, NamedTuple

from polars import DataFrame, Series
from PySide6.QtWidgets import QProgressBar

from solie.common import UniqueTask, get_sync_manager, spawn, spawn_blocking
from solie.utility import (
    ASSET_RECORD_SCHEMA,
    MAX_PREPARATION_STEPS,
    PROGRESS_BAR_MAX,
    SELECT_CANDLE_RANGE_SQL,
    SQLITE_TIMEOUT,
    AccountState,
    CandleDataStore,
    CandleRow,
    Cell,
    SavedStrategy,
    Strategy,
    VirtualPosition,
    VirtualState,
    create_empty_account_state,
    create_empty_asset_record,
    create_empty_candle_frame_schema,
    create_empty_unrealized_changes,
)
from solie.widget import GraphLines

from .analyze_market import ChunkSimulation, SimulationState, make_indicators

INDICATOR_LOOKBACK = timedelta(days=28)
INDICATOR_BATCH_SPAN = timedelta(days=1)
CANDLE_FIELDS = ("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME")


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

    asset_record: DataFrame
    unrealized_changes: Series
    scribbles: dict[Any, Any]
    account_state: AccountState


class SimulationProcessInput(NamedTuple):
    """Picklable input sent to the simulation worker process."""

    candle_rootpath: Path
    strategy: Strategy
    target_symbols: list[str]
    calculate_from_timestamp: int
    calculate_until_timestamp: int
    progress: ListProxy[int]


type CandleFrameRow = dict[str, int | float | None]


class SimulationMoment(NamedTuple):
    """One streamed timestamp waiting for indicator-backed simulation."""

    timestamp: int
    rows: dict[str, CandleRow]


class SimulationCalculator:
    """UI-facing wrapper around the process-owned streamed simulation."""

    def __init__(
        self,
        *,
        unique_task: UniqueTask,
        config: CalculationConfig,
        candle_data_store: CandleDataStore,
        widgets: WidgetReferences,
    ) -> None:
        """Initialize simulation calculator."""
        self.unique_task = unique_task
        self.candle_rootpath = candle_data_store.rootpath
        self.widgets = widgets

        self.year = config.year
        self.strategy = config.strategy
        self.target_symbols = config.target_symbols
        self.only_visible = config.only_visible
        self.should_draw_all_years = config.should_draw_all_years

        self.prepare_step = 0
        self.calculate_step = Cell(0)

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

        self.calculate_from = self.slice_from
        self.calculate_until = self.slice_until
        self.asset_record = create_empty_asset_record()
        self.unrealized_changes = create_empty_unrealized_changes()
        self.scribbles: dict[Any, Any] = {}
        self.account_state = create_empty_account_state(self.target_symbols)

    async def calculate(self) -> CalculationResult:
        """Run the simulation calculation."""
        bar_task = spawn(self._play_progress_bar())
        bar_task.add_done_callback(lambda _: self.widgets.pre_progressbar.setValue(0))
        bar_task.add_done_callback(lambda _: self.widgets.main_progressbar.setValue(0))
        self.unique_task.add_done_callback(lambda _: bar_task.cancel())

        self.prepare_step = 1
        self._reset_calculation_state()

        self.prepare_step = MAX_PREPARATION_STEPS
        if self.calculate_from < self.calculate_until:
            result = await self._run_process_calculation()
        else:
            result = self._create_result()

        self.prepare_step = MAX_PREPARATION_STEPS
        self.calculate_step.value = PROGRESS_BAR_MAX
        self.widgets.pre_progressbar.setValue(PROGRESS_BAR_MAX)
        self.widgets.main_progressbar.setValue(PROGRESS_BAR_MAX)
        return result

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

    def _reset_calculation_state(self) -> None:
        """Reset mutable calculation state for a new run."""
        if self.only_visible:
            graph_widget = self.widgets.simulation_graph.price_widget
            view_range = graph_widget.getAxis("bottom").range
            view_start = datetime.fromtimestamp(view_range[0], tz=UTC)
            view_end = datetime.fromtimestamp(view_range[1], tz=UTC)

            if self.should_draw_all_years:
                self.calculate_from = view_start
                self.calculate_until = view_end
            else:
                self.calculate_from = max(view_start, self.slice_from)
                self.calculate_until = min(view_end, self.slice_until)

        else:
            self.calculate_from = self.slice_from
            self.calculate_until = self.slice_until

        self.asset_record = self._create_initial_asset_record()
        self.unrealized_changes = create_empty_unrealized_changes()
        self.scribbles = {}
        self.account_state = create_empty_account_state(self.target_symbols)
        self.calculate_step.value = 0

    def _create_initial_asset_record(self) -> DataFrame:
        """Create the starting asset baseline row."""
        return _create_initial_asset_record(
            int(self.calculate_from.timestamp() * 1000),
        )

    async def _run_process_calculation(self) -> CalculationResult:
        """Run streamed simulation in the process pool."""
        progress = get_sync_manager().list([0])
        progress_task = spawn(self._sync_calculation_progress(progress))
        self.unique_task.add_done_callback(lambda _: progress_task.cancel())

        process_input = SimulationProcessInput(
            candle_rootpath=self.candle_rootpath,
            strategy=self._create_process_strategy(),
            target_symbols=self.target_symbols,
            calculate_from_timestamp=int(self.calculate_from.timestamp() * 1000),
            calculate_until_timestamp=int(self.calculate_until.timestamp() * 1000),
            progress=progress,
        )

        try:
            result = await spawn_blocking(
                calculate_streamed_simulation,
                process_input,
            )
        finally:
            progress_task.cancel()

        self.asset_record = result.asset_record
        self.unrealized_changes = result.unrealized_changes
        self.scribbles = result.scribbles
        self.account_state = result.account_state
        return self._create_result()

    async def _sync_calculation_progress(self, progress: ListProxy[int]) -> None:
        """Copy process-owned progress into the UI progress model."""
        while True:
            self.calculate_step.value = int(progress[0])
            await sleep(0.05)

    def _create_process_strategy(self) -> Strategy:
        """Create a picklable strategy instance for process execution."""
        if isinstance(self.strategy, SavedStrategy):
            return self.strategy.create_picklable_copy()
        return self.strategy

    def _create_result(self) -> CalculationResult:
        """Create the public calculation result from current state."""
        return CalculationResult(
            asset_record=self.asset_record,
            unrealized_changes=self.unrealized_changes,
            scribbles=self.scribbles,
            account_state=self.account_state,
        )


class StreamedSimulationRunner:
    """Process-local streamed simulation over SQLite candle rows."""

    def __init__(self, process_input: SimulationProcessInput) -> None:
        """Initialize process-local simulation state."""
        self.candle_rootpath = process_input.candle_rootpath
        self.strategy = process_input.strategy
        if isinstance(self.strategy, SavedStrategy):
            self.strategy.compile_code()

        self.target_symbols = process_input.target_symbols
        self.calculate_from_timestamp = process_input.calculate_from_timestamp
        self.calculate_until_timestamp = process_input.calculate_until_timestamp
        self.progress = process_input.progress
        self.reported_progress = 0

        self.window_rows: deque[CandleFrameRow] = deque()
        self.row_iterators: dict[str, Generator[CandleRow, None, None]] = {}
        self.next_rows: dict[str, CandleRow | None] = {}
        self.rows_at_timestamp: dict[str, CandleRow] = {}
        self.active_symbols: list[str] = []
        self.current_candle_data: dict[str, float] = {}
        self.current_indicators: dict[str, float] = {}
        self.pending_moments: list[SimulationMoment] = []
        self.total_milliseconds = max(
            self.calculate_until_timestamp - self.calculate_from_timestamp,
            1,
        )
        self.next_indicator_flush_timestamp = (
            self.calculate_from_timestamp
            + int(INDICATOR_BATCH_SPAN.total_seconds() * 1000)
        )

        self.asset_record = _create_initial_asset_record(
            self.calculate_from_timestamp,
        )
        self.unrealized_changes = create_empty_unrealized_changes()
        self.scribbles: dict[Any, Any] = {}
        self.account_state = create_empty_account_state(self.target_symbols)
        self.virtual_state = self._create_virtual_state()

    def run(self) -> CalculationResult:
        """Run the streamed simulation to completion."""
        simulator = ChunkSimulation(
            strategy=self.strategy,
            target_symbols=self.target_symbols,
            state=SimulationState(
                asset_record=self.asset_record,
                unrealized_changes=self.unrealized_changes,
                scribbles=self.scribbles,
                account_state=self.account_state,
                virtual_state=self.virtual_state,
            ),
        )

        with ExitStack() as stream_resources:
            self._prepare_candle_streams(
                self.calculate_from_timestamp
                - int(INDICATOR_LOOKBACK.total_seconds() * 1000),
                self.calculate_until_timestamp,
                stream_resources,
            )

            while True:
                timestamp = self._next_stream_timestamp()
                if timestamp is None:
                    break

                self._consume_stream_timestamp(timestamp)
                self._append_window_row(timestamp)

                if timestamp >= self.calculate_from_timestamp:
                    self.pending_moments.append(
                        SimulationMoment(
                            timestamp=timestamp,
                            rows=self.rows_at_timestamp.copy(),
                        ),
                    )
                    if timestamp >= self.next_indicator_flush_timestamp:
                        self._simulate_pending_moments(simulator)
                        self.next_indicator_flush_timestamp = (
                            timestamp
                            + int(INDICATOR_BATCH_SPAN.total_seconds() * 1000)
                        )

                self._trim_window_rows(self._trim_reference_timestamp(timestamp))

            self._simulate_pending_moments(simulator)
            self.progress[0] = PROGRESS_BAR_MAX

        output = simulator.finish()
        return CalculationResult(
            asset_record=output.asset_record,
            unrealized_changes=output.unrealized_changes,
            scribbles=output.scribbles,
            account_state=output.account_state,
        )

    def _create_virtual_state(self) -> VirtualState:
        """Create a blank mutable virtual account state."""
        virtual_state = VirtualState(
            available_balance=1,
            positions={},
            placements={},
        )
        for symbol in self.target_symbols:
            virtual_state.positions[symbol] = VirtualPosition(
                amount=0.0,
                entry_price=0.0,
            )
            virtual_state.placements[symbol] = {}
        return virtual_state

    def _prepare_candle_streams(
        self,
        provide_from_timestamp: int,
        calculate_until_timestamp: int,
        stream_resources: ExitStack,
    ) -> None:
        """Initialize per-symbol SQLite iterators for this run."""
        self.window_rows = deque()
        self.row_iterators = {}
        self.next_rows = {}
        self.rows_at_timestamp = {}
        self.active_symbols = []
        self.current_candle_data = {}
        self.current_indicators = {}
        self.pending_moments = []

        for symbol in self.target_symbols:
            iterator = self._iter_candle_range(
                symbol,
                provide_from_timestamp,
                calculate_until_timestamp,
            )
            stream_resources.callback(iterator.close)
            row = next(iterator, None)
            if row is None:
                continue
            self.row_iterators[symbol] = iterator
            self.next_rows[symbol] = row

    def _iter_candle_range(
        self,
        symbol: str,
        start_timestamp: int,
        end_timestamp: int,
    ) -> Generator[CandleRow, None, None]:
        """Iterate one symbol's SQLite candle rows across touched year files."""
        for year in _iter_years(start_timestamp, end_timestamp):
            filepath = self.candle_rootpath / str(year) / f"{symbol}.sqlite"
            if not filepath.exists():
                continue
            year_start = max(start_timestamp, _year_start_timestamp(year))
            year_end = min(end_timestamp, _year_end_timestamp(year))
            with ExitStack() as resources:
                connection = sqlite3.connect(filepath, timeout=SQLITE_TIMEOUT)
                resources.callback(connection.close)
                _configure_read_connection(connection)
                cursor = connection.execute(
                    SELECT_CANDLE_RANGE_SQL,
                    (year_start, year_end),
                )
                resources.callback(cursor.close)
                for row in cursor:
                    yield CandleRow(
                        int(row[0]),
                        float(row[1]),
                        float(row[2]),
                        float(row[3]),
                        float(row[4]),
                        float(row[5]),
                    )

    def _next_stream_timestamp(self) -> int | None:
        """Get the next timestamp available from any symbol stream."""
        available_timestamps = [
            row.timestamp for row in self.next_rows.values() if row is not None
        ]
        if len(available_timestamps) == 0:
            return None
        return min(available_timestamps)

    def _consume_stream_timestamp(self, timestamp: int) -> None:
        """Collect rows at the next timestamp and advance their iterators."""
        self.rows_at_timestamp = {}
        for symbol, row in list(self.next_rows.items()):
            if row is None or row.timestamp != timestamp:
                continue
            self.rows_at_timestamp[symbol] = row
            self.next_rows[symbol] = next(self.row_iterators[symbol], None)

    def _trim_reference_timestamp(self, timestamp: int) -> int:
        """Keep lookback rows needed by the oldest unprocessed moment."""
        if len(self.pending_moments) > 0:
            return self.pending_moments[0].timestamp
        return timestamp

    def _append_window_row(self, timestamp: int) -> None:
        """Append the current timestamp's symbol rows to the indicator window."""
        row_data: CandleFrameRow = {"timestamp": timestamp}
        for symbol in self.target_symbols:
            for field in CANDLE_FIELDS:
                row_data[f"{symbol}/{field}"] = None

        for symbol, row in self.rows_at_timestamp.items():
            row_data[f"{symbol}/OPEN"] = row.open
            row_data[f"{symbol}/HIGH"] = row.high
            row_data[f"{symbol}/LOW"] = row.low
            row_data[f"{symbol}/CLOSE"] = row.close
            row_data[f"{symbol}/VOLUME"] = row.volume

        self.window_rows.append(row_data)

    def _trim_window_rows(self, timestamp: int) -> None:
        """Keep the indicator window bounded to the lookback horizon."""
        oldest_timestamp = timestamp - int(INDICATOR_LOOKBACK.total_seconds() * 1000)
        while len(self.window_rows) > 0:
            row_timestamp = self.window_rows[0]["timestamp"]
            if not isinstance(row_timestamp, int) or row_timestamp >= oldest_timestamp:
                return
            self.window_rows.popleft()

    def _create_window_frame(self) -> DataFrame:
        """Create the bounded Polars frame needed by indicator scripts."""
        return DataFrame(
            list(self.window_rows),
            schema=create_empty_candle_frame_schema(self.target_symbols),
        )

    def _simulate_pending_moments(self, simulator: ChunkSimulation) -> None:
        """Run sequential simulation for the current indicator batch."""
        if len(self.pending_moments) == 0:
            return

        window_frame = self._create_window_frame()
        candle_rows = self._collect_pending_frame_rows(window_frame.interpolate())
        indicators = make_indicators(
            self.strategy,
            self.target_symbols,
            window_frame,
        )
        indicator_rows = self._collect_pending_frame_rows(indicators)

        for moment in self.pending_moments:
            self.rows_at_timestamp = moment.rows
            self._update_active_symbols()
            if len(self.active_symbols) > 0:
                self._update_current_candle_data(
                    candle_rows.get(moment.timestamp, {}),
                )
                self._update_current_indicators(
                    indicator_rows.get(moment.timestamp, {}),
                )
                simulator.simulate_moment(
                    timestamp=moment.timestamp,
                    active_symbols=self.active_symbols,
                    current_candle_data=self.current_candle_data,
                    current_indicators=self.current_indicators,
                )
            self._update_calculation_progress(moment.timestamp)

        self.pending_moments = []

    def _collect_pending_frame_rows(
        self,
        frame: DataFrame,
    ) -> dict[int, dict[str, Any]]:
        """Collect the latest frame row for each pending timestamp."""
        frame_rows: dict[int, dict[str, Any]] = {}
        pending_moments = sorted(
            self.pending_moments,
            key=lambda moment: moment.timestamp,
        )
        pending_index = 0
        latest_indicator_row: dict[str, Any] = {}

        for row in frame.iter_rows(named=True):
            timestamp = row.get("timestamp")
            if not isinstance(timestamp, Real):
                continue

            row_timestamp = int(timestamp)
            while (
                pending_index < len(pending_moments)
                and pending_moments[pending_index].timestamp < row_timestamp
            ):
                if len(latest_indicator_row) > 0:
                    frame_rows[pending_moments[pending_index].timestamp] = (
                        latest_indicator_row
                    )
                pending_index += 1

            latest_indicator_row = row
            while (
                pending_index < len(pending_moments)
                and pending_moments[pending_index].timestamp == row_timestamp
            ):
                frame_rows[pending_moments[pending_index].timestamp] = (
                    latest_indicator_row
                )
                pending_index += 1

        while pending_index < len(pending_moments):
            if len(latest_indicator_row) > 0:
                frame_rows[pending_moments[pending_index].timestamp] = (
                    latest_indicator_row
                )
            pending_index += 1

        return frame_rows

    def _update_active_symbols(self) -> None:
        """Set symbols that have a candle row at the current timestamp."""
        self.active_symbols = [
            symbol for symbol in self.target_symbols if symbol in self.rows_at_timestamp
        ]

    def _update_current_candle_data(self, candle_row: dict[str, Any]) -> None:
        """Create the strategy-facing candle dict for the current timestamp."""
        current_candle_data: dict[str, float] = {}
        for symbol in self.target_symbols:
            for field in CANDLE_FIELDS:
                column = f"{symbol}/{field}"
                value = candle_row.get(column)
                if isinstance(value, Real):
                    current_candle_data[column] = float(value)
                else:
                    current_candle_data[column] = math.nan
        self.current_candle_data = current_candle_data

    def _update_current_indicators(self, indicator_row: dict[str, Any]) -> None:
        """Create the strategy-facing indicator dict for the current timestamp."""
        if len(indicator_row) == 0:
            self.current_indicators = {}
            return

        current_indicators: dict[str, float] = {}
        for column, value in indicator_row.items():
            if column == "timestamp":
                continue
            if isinstance(value, Real):
                current_indicators[column] = float(value)
            else:
                current_indicators[column] = math.nan
        self.current_indicators = current_indicators

    def _update_calculation_progress(self, timestamp: int) -> None:
        """Update process-visible progress from a processed timestamp."""
        new_progress = min(
            PROGRESS_BAR_MAX,
            math.ceil(
                (timestamp - self.calculate_from_timestamp)
                * PROGRESS_BAR_MAX
                / self.total_milliseconds,
            ),
        )
        if new_progress <= self.reported_progress:
            return
        self.reported_progress = new_progress
        self.progress[0] = new_progress


def calculate_streamed_simulation(
    process_input: SimulationProcessInput,
) -> CalculationResult:
    """Run streamed simulation inside a process-pool worker."""
    runner = StreamedSimulationRunner(process_input)
    return runner.run()


def _create_initial_asset_record(timestamp: int) -> DataFrame:
    """Create the starting asset baseline row."""
    return DataFrame(
        [
            {
                "timestamp": timestamp,
                "CAUSE": "OTHER",
                "SYMBOL": None,
                "SIDE": None,
                "FILL_PRICE": None,
                "ROLE": None,
                "MARGIN_RATIO": None,
                "ORDER_ID": None,
                "RESULT_ASSET": 1.0,
            },
        ],
        schema=ASSET_RECORD_SCHEMA,
    )


def _configure_read_connection(connection: Connection) -> None:
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA busy_timeout = 5000")


def _year(timestamp: int) -> int:
    return datetime.fromtimestamp(timestamp / 1000, tz=UTC).year


def _iter_years(start_timestamp: int, end_timestamp: int) -> range:
    return range(_year(start_timestamp), _year(end_timestamp) + 1)


def _year_start_timestamp(year: int) -> int:
    return int(datetime(year, 1, 1, tzinfo=UTC).timestamp() * 1000)


def _year_end_timestamp(year: int) -> int:
    return int(datetime(year + 1, 1, 1, tzinfo=UTC).timestamp() * 1000) - 1
