import pickle
from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

import aiofiles
import aiofiles.os
import numpy as np
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6.QtWidgets import QMenu
from scipy.signal import find_peaks

from solie.common import UniqueTask, outsource, spawn, spawn_blocking
from solie.logic import (
    CalculationConfig,
    SimulationCalculator,
    WidgetReferences,
    make_indicators,
)
from solie.utility import (
    MIN_PEAK_COUNT,
    AccountState,
    DurationRecorder,
    PositionDirection,
    RWLock,
    SimulationSettings,
    SimulationSummary,
    create_empty_account_state,
    create_empty_asset_record,
    create_empty_unrealized_changes,
    sort_data_frame,
    sort_series,
    to_moment,
)
from solie.widget import ask
from solie.window import Window

from .united import team


class DisplayTimeRange(NamedTuple):
    """Time range configuration for display."""

    years: list[int]
    slice_from: datetime
    slice_until: datetime


class CandleDataPair(NamedTuple):
    """Pair of original and sliced candle data."""

    original: pd.DataFrame
    sliced: pd.DataFrame


class AssetRecordData(NamedTuple):
    """Asset record with historical values."""

    record: pd.DataFrame
    last_asset: float | None
    before_asset: float | None


class RangeMetrics(NamedTuple):
    """Metrics calculated for a visible range."""

    total_change_count: int
    symbol_change_count: int
    total_margin_ratio: float
    symbol_margin_ratio: float
    total_yield: float
    symbol_yield: float
    min_unrealized_change: float


class ChunkList(NamedTuple):
    """List of chunks and their count."""

    chunks: list[pd.DataFrame]
    chunk_count: int


class Simulator:
    def __init__(self, window: Window, scheduler: AsyncIOScheduler) -> None:
        self._window = window
        self._scheduler = scheduler
        self._workerpath = window.datapath / "simulator"

        self._line_display_task = UniqueTask()
        self._range_display_task = UniqueTask()
        self._calculation_task = UniqueTask()

        self._viewing_symbol = window.data_settings.target_symbols[0]
        self._should_draw_all_years = False

        self._simulation_settings = SimulationSettings(
            year=datetime.now(timezone.utc).year,
        )
        self._simulation_summary: SimulationSummary | None = None

        self._raw_account_state = create_empty_account_state(
            self._window.data_settings.target_symbols
        )
        self._raw_scribbles: dict[Any, Any] = {}
        self._raw_asset_record = RWLock(create_empty_asset_record())
        self._raw_unrealized_changes = RWLock(create_empty_unrealized_changes())

        self._account_state = create_empty_account_state(
            self._window.data_settings.target_symbols
        )
        self._scribbles: dict[Any, Any] = {}
        self._asset_record = RWLock(create_empty_asset_record())
        self._unrealized_changes = RWLock(create_empty_unrealized_changes())

        self._scheduler.add_job(
            self.display_available_years,
            trigger="cron",
            hour="*",
        )
        self._scheduler.add_job(
            self.display_lines,
            trigger="cron",
            hour="*",
            kwargs={"periodic": True},
        )

        self._connect_ui_events()

    def _connect_ui_events(self):
        window = self._window

        job = self._display_range_information
        outsource(window.simulation_graph.price_widget.sigRangeChanged, job)
        job = self._set_minimum_view_range
        outsource(window.simulation_graph.price_widget.sigRangeChanged, job)
        job = self._update_calculation_settings
        outsource(window.comboBox.currentIndexChanged, job)
        job = self._calculate
        outsource(window.pushButton_3.clicked, job)
        job = self._update_presentation_settings
        outsource(window.spinBox_2.editingFinished, job)
        job = self._update_presentation_settings
        outsource(window.doubleSpinBox.editingFinished, job)
        job = self._update_presentation_settings
        outsource(window.doubleSpinBox_2.editingFinished, job)
        job = self._erase
        outsource(window.pushButton_4.clicked, job)
        job = self._update_calculation_settings
        outsource(window.comboBox_5.currentIndexChanged, job)
        job = self._toggle_combined_draw
        outsource(window.checkBox_3.toggled, job)
        job = self.display_year_range
        outsource(window.pushButton_15.clicked, job)
        job = self._delete_calculation_data
        outsource(window.pushButton_16.clicked, job)
        job = self._draw
        outsource(window.pushButton_17.clicked, job)
        job = self._update_viewing_symbol
        outsource(window.comboBox_6.currentIndexChanged, job)

        action_menu = QMenu(window)
        window.pushButton_11.setMenu(action_menu)

        text = "Calculate temporarily only on visible range"
        job = self._simulate_only_visible
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Stop calculation"
        job = self._stop_calculation
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Find spots with lowest unrealized profit"
        job = self._analyze_unrealized_peaks
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Display same range as transaction graph"
        job = self._match_graph_range
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)

    async def load_work(self) -> None:
        await aiofiles.os.makedirs(self._workerpath, exist_ok=True)

        text = "Nothing drawn"
        self._window.label_19.setText(text)

    async def dump_work(self) -> None:
        pass

    async def _update_viewing_symbol(self) -> None:
        alias = self._window.comboBox_6.currentText()
        symbol = self._window.alias_to_symbol[alias]
        self._viewing_symbol = symbol

        await self.display_lines()

    async def _update_calculation_settings(self) -> None:
        text = self._window.comboBox_5.currentText()
        if text == "":
            return
        from_year = self._simulation_settings.year
        to_year = int(text)
        self._simulation_settings.year = to_year
        if from_year != to_year:
            spawn(self.display_year_range())

        index = self._window.comboBox.currentIndex()
        self._simulation_settings.strategy_index = index

        await self.display_lines()

    async def _update_presentation_settings(self) -> None:
        input_value = self._window.spinBox_2.value()
        self._simulation_settings.leverage = input_value
        input_value = self._window.doubleSpinBox.value()
        self._simulation_settings.taker_fee = input_value
        input_value = self._window.doubleSpinBox_2.value()
        self._simulation_settings.maker_fee = input_value
        await self.present()

    async def display_lines(self, periodic=False) -> None:
        self._line_display_task.spawn(self._display_lines_real(periodic))

    def _get_display_time_range(self) -> DisplayTimeRange:
        """Calculate time range and years for display."""
        if self._should_draw_all_years:
            years = []
            slice_from = datetime.fromtimestamp(0, tz=timezone.utc)
            slice_until = datetime.now(timezone.utc)
            slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
        else:
            year = self._simulation_settings.year
            years = [year]
            slice_from = datetime(year, 1, 1, tzinfo=timezone.utc)
            if year == datetime.now(timezone.utc).year:
                slice_until = datetime.now(timezone.utc)
                slice_until = slice_until.replace(minute=0, second=0, microsecond=0)
            else:
                slice_until = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        slice_until -= timedelta(seconds=1)
        return DisplayTimeRange(
            years=years, slice_from=slice_from, slice_until=slice_until
        )

    async def _load_and_prepare_candle_data(
        self, years: list[int], slice_from: datetime
    ) -> CandleDataPair:
        """Load candle data for specified years."""
        divided_datas: list[pd.DataFrame] = []
        for year in years:
            more_df = await team.collector.read_saved_candle_data(year)
            divided_datas.append(more_df)
        candle_data_original = await spawn_blocking(pd.concat, divided_datas)
        if not candle_data_original.index.is_monotonic_increasing:
            candle_data_original = await spawn_blocking(
                sort_data_frame, candle_data_original
            )
        candle_data = candle_data_original[slice_from:]
        return CandleDataPair(original=candle_data_original, sliced=candle_data)

    async def _prepare_asset_record(
        self, slice_from: datetime, candle_data: pd.DataFrame
    ) -> AssetRecordData:
        """Prepare asset record with historical data."""
        async with self._asset_record.read_lock as cell:
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

        if len(candle_data) > 0:
            last_written_moment = candle_data.index[-1]
            new_moment = last_written_moment + timedelta(seconds=10)
            new_index = candle_data.index.union([new_moment])
            candle_data = candle_data.reindex(new_index)

        return AssetRecordData(
            record=asset_record, last_asset=last_asset, before_asset=before_asset
        )

    async def _update_asset_record_with_observations(
        self,
        asset_record: pd.DataFrame,
        last_asset: float | None,
        before_asset: float | None,
        slice_from: datetime,
    ) -> pd.DataFrame:
        """Update asset record with latest observations."""
        if last_asset is not None:
            observed_until = self._account_state.observed_until
            if len(asset_record) == 0 or asset_record.index[-1] < observed_until:
                if slice_from < observed_until:
                    asset_record.loc[observed_until, "CAUSE"] = "OTHER"
                    asset_record.loc[observed_until, "RESULT_ASSET"] = last_asset
                    if not asset_record.index.is_monotonic_increasing:
                        asset_record = await spawn_blocking(
                            sort_data_frame, asset_record
                        )

        if before_asset is not None:
            asset_record.loc[slice_from, "CAUSE"] = "OTHER"
            asset_record.loc[slice_from, "RESULT_ASSET"] = before_asset
            if not asset_record.index.is_monotonic_increasing:
                asset_record = await spawn_blocking(sort_data_frame, asset_record)

        return asset_record

    async def _display_lines_real(self, periodic: bool) -> None:
        symbol = self._viewing_symbol
        strategy_index = self._simulation_settings.strategy_index
        strategy = team.strategist.strategies[strategy_index]

        async with team.collector.candle_data.read_lock as cell:
            if len(cell.data) == 0:
                return

        if periodic:
            current_moment = to_moment(datetime.now(timezone.utc))
            before_moment = current_moment - timedelta(seconds=10)
            for _ in range(50):
                async with team.collector.candle_data.read_lock as cell:
                    if cell.data.index[-1] == before_moment:
                        break
                await sleep(0.1)

        duration_recorder = DurationRecorder("DISPLAY_SIMULATION_LINES")

        time_range = self._get_display_time_range()
        years = time_range.years
        if self._should_draw_all_years:
            years = await team.collector.check_saved_years()

        position = self._account_state.positions[symbol]
        entry_price = (
            None
            if position.direction == PositionDirection.NONE
            else position.entry_price
        )

        await self._window.simulation_graph.update_light_lines(
            mark_prices=[],
            aggregate_trades=[],
            book_tickers=[],
            entry_price=entry_price,
            observed_until=self._account_state.observed_until,
        )

        candle_pair = await self._load_and_prepare_candle_data(
            years, time_range.slice_from
        )

        async with self._unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data.copy()

        asset_data = await self._prepare_asset_record(
            time_range.slice_from, candle_pair.sliced
        )

        asset_record = await self._update_asset_record_with_observations(
            asset_data.record,
            asset_data.last_asset,
            asset_data.before_asset,
            time_range.slice_from,
        )

        await self._window.simulation_graph.update_heavy_lines(
            symbol=symbol,
            candle_data=candle_pair.sliced,
            asset_record=asset_record,
            unrealized_changes=unrealized_changes,
        )

        indicators = await spawn_blocking(
            make_indicators,
            strategy=strategy,
            target_symbols=[self._viewing_symbol],
            candle_data=candle_pair.original,
        )
        indicators = indicators[time_range.slice_from : time_range.slice_until]

        await self._window.simulation_graph.update_custom_lines(symbol, indicators)
        duration_recorder.record()
        await self._set_minimum_view_range()

    async def _erase(self) -> None:
        self._raw_account_state = create_empty_account_state(
            self._window.data_settings.target_symbols
        )
        self._raw_scribbles = {}
        self._raw_asset_record = RWLock(create_empty_asset_record())
        self._raw_unrealized_changes = RWLock(create_empty_unrealized_changes())
        self._simulation_summary = None

        await self.present()

    async def display_available_years(self) -> None:
        years = await team.collector.check_saved_years()
        years.sort(reverse=True)

        widget = self._window.comboBox_5
        choices = [int(widget.itemText(i)) for i in range(widget.count())]
        choices.sort(reverse=True)

        if years != choices:
            self._window.comboBox_5.clear()
            self._window.comboBox_5.addItems([str(y) for y in years])

    async def _simulate_only_visible(self) -> None:
        await self._calculate(only_visible=True)

    async def _display_range_information(self) -> None:
        self._range_display_task.spawn(self._display_range_information_real())

    def _calculate_range_metrics(
        self,
        asset_record: pd.DataFrame,
        asset_changes: pd.Series,
        symbol_mask: pd.Series,
        unrealized_changes: pd.Series,
    ) -> RangeMetrics:
        """Calculate various metrics for the visible range."""
        total_change_count = len(asset_changes)
        symbol_change_count = len(asset_changes[symbol_mask])

        total_margin_ratio = (
            asset_record["MARGIN_RATIO"].sum() if len(asset_record) > 0 else 0
        )
        symbol_margin_ratio = (
            asset_record[symbol_mask]["MARGIN_RATIO"].sum()
            if len(asset_record[symbol_mask]) > 0
            else 0
        )

        if len(asset_changes) > 0:
            total_yield = (asset_changes.cumprod().iloc[-1] - 1) * 100
        else:
            total_yield = 0

        if len(asset_changes[symbol_mask]) > 0:
            symbol_yield = (asset_changes[symbol_mask].cumprod().iloc[-1] - 1) * 100
        else:
            symbol_yield = 0

        min_unrealized_change = (
            unrealized_changes.min() if len(unrealized_changes) > 0 else 0.0
        )

        return RangeMetrics(
            total_change_count=total_change_count,
            symbol_change_count=symbol_change_count,
            total_margin_ratio=total_margin_ratio,
            symbol_margin_ratio=symbol_margin_ratio,
            total_yield=total_yield,
            symbol_yield=symbol_yield,
            min_unrealized_change=min_unrealized_change,
        )

    async def _display_range_information_real(self) -> None:
        symbol = self._viewing_symbol
        price_widget = self._window.simulation_graph.price_widget

        range_start_timestamp = max(price_widget.getAxis("bottom").range[0], 0.0)
        range_start = datetime.fromtimestamp(range_start_timestamp, tz=timezone.utc)

        range_end_timestamp = price_widget.getAxis("bottom").range[1]
        range_end_timestamp = (
            9223339636
            if range_end_timestamp < 0
            else min(range_end_timestamp, 9223339636.0)
        )
        range_end = datetime.fromtimestamp(range_end_timestamp, tz=timezone.utc)

        range_length = range_end - range_start
        range_days = range_length.days
        range_hours, remains = divmod(range_length.seconds, 3600)
        range_minutes, _ = divmod(remains, 60)

        async with self._unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data[range_start:range_end].copy()
        async with self._asset_record.read_lock as cell:
            asset_record = cell.data[range_start:range_end].copy()

        auto_trade_mask = asset_record["CAUSE"] == "AUTO_TRADE"
        asset_changes = asset_record["RESULT_ASSET"].pct_change(fill_method=None) + 1
        asset_record = asset_record[auto_trade_mask]
        asset_changes = asset_changes.reindex(asset_record.index, fill_value=1.0)
        symbol_mask = asset_record["SYMBOL"] == symbol

        view_range = price_widget.getAxis("left").range
        price_range_height = (1 - view_range[0] / view_range[1]) * 100

        metrics = self._calculate_range_metrics(
            asset_record, asset_changes, symbol_mask, unrealized_changes
        )

        text = (
            f"Visible time range {range_days}d {range_hours}h {range_minutes}s"
            "  ⦁  "
            f"Visible price range {price_range_height:.2f}%"
            "  ⦁  "
            f"Transaction count {metrics.symbol_change_count}({metrics.total_change_count})"
            "  ⦁  "
            f"Transaction amount *{metrics.symbol_margin_ratio:.4f}({metrics.total_margin_ratio:.4f})"
            "  ⦁  "
            f"Total realized profit {metrics.symbol_yield:+.4f}({metrics.total_yield:+.4f})%"
            "  ⦁  "
            f"Lowest unrealized profit {metrics.min_unrealized_change * 100:+.4f}%"
        )
        self._window.label_13.setText(text)

    async def _set_minimum_view_range(self) -> None:
        widget = self._window.simulation_graph.price_widget
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore
        widget = self._window.simulation_graph.asset_widget
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore

    async def _calculate(self, only_visible=False) -> None:
        unique_task = self._calculation_task
        unique_task.spawn(self._calculate_real(unique_task, only_visible))

    async def _calculate_real(
        self, unique_task: UniqueTask, only_visible: bool
    ) -> None:
        year = self._simulation_settings.year
        strategy_index = self._simulation_settings.strategy_index
        strategy = team.strategist.strategies[strategy_index]

        year_candle_data = await team.collector.read_saved_candle_data(year)

        config = CalculationConfig(
            year=year,
            strategy=strategy,
            target_symbols=self._window.data_settings.target_symbols,
            only_visible=only_visible,
            should_draw_all_years=self._should_draw_all_years,
        )

        widgets = WidgetReferences(
            pre_progressbar=self._window.progressBar_4,
            main_progressbar=self._window.progressBar,
            simulation_graph=self._window.simulation_graph,
        )

        calculator = SimulationCalculator(
            unique_task=unique_task,
            config=config,
            workerpath=self._workerpath,
            year_candle_data=year_candle_data,
            widgets=widgets,
        )

        result = await calculator.calculate()

        self._raw_asset_record = RWLock(result.asset_record)
        self._raw_unrealized_changes = RWLock(result.unrealized_changes)
        self._raw_scribbles = result.scribbles
        self._raw_account_state = result.account_state
        self._simulation_summary = SimulationSummary(
            year=year,
            strategy_code_name=strategy.code_name,
            strategy_version=strategy.version,
        )
        await self.present()

    def _calculate_chunk_asset_changes(
        self,
        chunk_asset_record: pd.DataFrame,
        maker_fee: float,
        taker_fee: float,
        leverage: int,
    ) -> pd.Series:
        """Calculate asset changes for a single chunk."""
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

        chunk_fees = chunk_asset_record["ROLE"].copy()
        chunk_fees[chunk_fees == "MAKER"] = maker_fee
        chunk_fees[chunk_fees == "TAKER"] = taker_fee
        chunk_fees = chunk_fees.astype(np.float32)
        chunk_margin_ratios = chunk_asset_record["MARGIN_RATIO"]
        chunk_asset_changes_by_fee = (
            1 - (chunk_fees / 100) * chunk_margin_ratios * leverage
        )

        return chunk_asset_changes_by_leverage * chunk_asset_changes_by_fee

    def _prepare_chunk_list(self, asset_record: pd.DataFrame) -> ChunkList:
        """Prepare list of asset record chunks based on strategy settings."""
        if self._simulation_summary is None:
            return ChunkList(chunks=[asset_record], chunk_count=1)

        strategy_index = self._simulation_settings.strategy_index
        strategy = team.strategist.strategies[strategy_index]
        parallel_chunk_days = strategy.parallel_simulation_chunk_days

        if parallel_chunk_days is None:
            return ChunkList(chunks=[asset_record], chunk_count=1)

        division = timedelta(days=parallel_chunk_days)
        grouper = pd.Grouper(freq=division, origin="epoch")  # type:ignore
        grouped = asset_record.groupby(grouper)
        chunk_list = [r.dropna() for _, r in grouped]
        return ChunkList(chunks=chunk_list, chunk_count=len(chunk_list))

    async def present(self) -> None:
        maker_fee = self._simulation_settings.maker_fee
        taker_fee = self._simulation_settings.taker_fee
        leverage = self._simulation_settings.leverage

        async with self._raw_asset_record.read_lock as cell:
            asset_record = cell.data.copy()
        async with self._raw_unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data.copy()

        scribbles = self._raw_scribbles.copy()
        account_state = self._raw_account_state.model_copy(deep=True)

        chunk_data = self._prepare_chunk_list(asset_record)

        chunk_asset_changes_list: list[pd.Series] = [
            self._calculate_chunk_asset_changes(
                chunk_data.chunks[turn], maker_fee, taker_fee, leverage
            )
            for turn in range(chunk_data.chunk_count)
        ]

        unrealized_changes = unrealized_changes * leverage
        year_asset_changes: pd.Series = pd.concat(chunk_asset_changes_list)
        if not year_asset_changes.index.is_monotonic_increasing:
            year_asset_changes = await spawn_blocking(sort_series, year_asset_changes)

        if len(asset_record) > 0:
            year_asset_changes[asset_record.index[0]] = 1.0
            if not year_asset_changes.index.is_monotonic_increasing:
                year_asset_changes = await spawn_blocking(
                    sort_series, year_asset_changes
                )

        asset_record = asset_record.reindex(year_asset_changes.index)
        asset_record["RESULT_ASSET"] = year_asset_changes.cumprod()

        self._scribbles = scribbles.copy()
        self._account_state = account_state.model_copy(deep=True)
        async with self._unrealized_changes.write_lock as cell:
            cell.data = unrealized_changes.copy()
        async with self._asset_record.write_lock as cell:
            cell.data = asset_record.copy()

        spawn(self.display_lines())
        spawn(self._display_range_information())

        if self._simulation_summary is None:
            self._window.label_19.setText("Nothing drawn")
        else:
            text = (
                f"Target year {self._simulation_summary.year}"
                "  ⦁  "
                f"Strategy code name {self._simulation_summary.strategy_code_name}"
                "  ⦁  "
                f"Strategy version {self._simulation_summary.strategy_version}"
            )
            self._window.label_19.setText(text)

    async def display_year_range(self) -> None:
        range_start = datetime(
            year=self._simulation_settings.year,
            month=1,
            day=1,
            tzinfo=timezone.utc,
        )
        range_start = range_start.timestamp()
        range_end = datetime(
            year=self._simulation_settings.year + 1,
            month=1,
            day=1,
            tzinfo=timezone.utc,
        )
        range_end = range_end.timestamp()
        widget = self._window.simulation_graph.price_widget
        widget.setXRange(range_start, range_end)

    async def _delete_calculation_data(self) -> None:
        year = self._simulation_settings.year
        strategy_index = self._simulation_settings.strategy_index

        strategy = team.strategist.strategies[strategy_index]
        strategy_code_name = strategy.code_name
        strategy_version = strategy.version

        workerpath = self._workerpath
        prefix = f"{strategy_code_name}_{strategy_version}_{year}"
        filepaths = [
            workerpath / f"{prefix}_asset_record.pickle",
            workerpath / f"{prefix}_unrealized_changes.pickle",
            workerpath / f"{prefix}_scribbles.pickle",
            workerpath / f"{prefix}_account_state.pickle",
            workerpath / f"{prefix}_virtual_state.pickle",
        ]

        does_file_exist = False
        for filepath in filepaths:
            if await aiofiles.os.path.isfile(filepath):
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

        for filepath in filepaths:
            if await aiofiles.os.path.isfile(filepath):
                await aiofiles.os.remove(filepath)

        await self._erase()

    async def _draw(self) -> None:
        year = self._simulation_settings.year
        strategy_index = self._simulation_settings.strategy_index

        strategy = team.strategist.strategies[strategy_index]
        strategy_code_name = strategy.code_name
        strategy_version = strategy.version

        workerpath = self._workerpath
        prefix = f"{strategy_code_name}_{strategy_version}_{year}"
        asset_record_path = workerpath / f"{prefix}_asset_record.pickle"
        unrealized_changes_path = workerpath / f"{prefix}_unrealized_changes.pickle"
        scribbles_path = workerpath / f"{prefix}_scribbles.pickle"
        account_state_path = workerpath / f"{prefix}_account_state.pickle"

        try:
            async with self._raw_asset_record.write_lock as cell:
                new = await spawn_blocking(pd.read_pickle, asset_record_path)
                cell.data = new
            async with self._raw_unrealized_changes.write_lock as cell:
                new = await spawn_blocking(pd.read_pickle, unrealized_changes_path)
                cell.data = new
            async with aiofiles.open(scribbles_path, "rb") as file:
                content = await file.read()
                self._raw_scribbles = pickle.loads(content)
            async with aiofiles.open(account_state_path, "rb") as file:
                content = await file.read()
                self._raw_account_state: AccountState = pickle.loads(content)
            self._simulation_summary = SimulationSummary(
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

    async def _match_graph_range(self) -> None:
        graph_from = self._window.transaction_graph.price_widget
        graph_to = self._window.simulation_graph.price_widget
        graph_range = graph_from.getAxis("bottom").range
        range_start = graph_range[0]
        range_end = graph_range[1]
        graph_to.setXRange(range_start, range_end, padding=0)  # type:ignore

    async def _stop_calculation(self) -> None:
        if self._calculation_task is not None:
            self._calculation_task.cancel()

    async def _analyze_unrealized_peaks(self) -> None:
        async with self._unrealized_changes.read_lock as cell:
            peak_indexes, _ = find_peaks(-cell.data, distance=3600 / 10)
            peak_sr = cell.data.iloc[peak_indexes]
        peak_sr = peak_sr.sort_values().iloc[:MIN_PEAK_COUNT]
        if len(peak_sr) < MIN_PEAK_COUNT:
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

    async def _toggle_combined_draw(self) -> None:
        is_checked = self._window.checkBox_3.isChecked()
        if is_checked:
            self._should_draw_all_years = True
        else:
            self._should_draw_all_years = False
        await self.display_lines()
