"""Live trading execution and account management worker."""

import math
import pickle
import webbrowser
from asyncio import gather, sleep
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Any, NamedTuple

import aiofiles
import aiofiles.os
import numpy as np
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6.QtWidgets import QMenu

from solie.common import UniqueTask, outsource, spawn, spawn_blocking
from solie.logic import (
    AccountListener,
    BinanceWatcher,
    DecisionContext,
    ExchangeConfig,
    OrderPlacer,
    OrderPlacerConfig,
    StateConfig,
    make_decisions,
    make_indicators,
)
from solie.overlay import LongTextView
from solie.utility import (
    ApiRequester,
    ApiRequestError,
    ApiStreamer,
    BookTicker,
    Decision,
    DurationRecorder,
    OrderType,
    PositionDirection,
    RWLock,
    Strategy,
    TransactionSettings,
    create_empty_account_state,
    create_empty_asset_record,
    create_empty_unrealized_changes,
    internet_connected,
    slice_deque,
    sort_data_frame,
    sort_series,
    to_moment,
    when_internet_connected,
    when_internet_disconnected,
)
from solie.widget import ask, overlay
from solie.window import Window

from .united import team

logger = getLogger(__name__)


class DisplayTimeRange(NamedTuple):
    """Time range configuration for transaction display."""

    get_from: datetime
    slice_from: datetime
    slice_until: datetime


class RealtimeData(NamedTuple):
    """Filtered realtime market data."""

    mark_prices: list[Any]  # list[MarkPrice]
    book_tickers: list[Any]  # list[BookTicker]
    aggregate_trades: list[Any]


class TransactionAssetData(NamedTuple):
    """Asset record with candle and historical data."""

    candle_original: pd.DataFrame
    candle_sliced: pd.DataFrame
    asset_record: pd.DataFrame
    last_asset: float | None
    before_asset: float | None


class TradeMetrics(NamedTuple):
    """Trade metrics for displaying transaction information."""

    total_change_count: int
    symbol_change_count: int
    total_margin_ratio: float
    symbol_margin_ratio: float
    total_yield: float
    symbol_yield: float


class IndicatorData(NamedTuple):
    """Current candle and indicator values."""

    current_candle_data: dict[str, float]
    current_indicators: dict[str, float]


class Transactor:
    """Worker for executing live trades on Binance."""

    def __init__(self, window: Window, scheduler: AsyncIOScheduler) -> None:
        """Initialize live transactor."""
        self._window = window
        self._scheduler = scheduler
        self._workerpath = window.datapath / "transactor"

        self._line_display_task = UniqueTask()
        self._range_display_task = UniqueTask()

        # Exchange configuration shared between components
        self._exchange_config = ExchangeConfig(
            maximum_quantities={},
            minimum_notionals={},
            price_precisions={},
            quantity_precisions={},
            maximum_leverages={},
            leverages={},
        )
        self._is_key_restrictions_satisfied = True

        self._api_requester = ApiRequester()

        self._viewing_symbol = window.data_settings.target_symbols[0]
        self._should_draw_frequently = True

        self._account_state = create_empty_account_state(
            window.data_settings.target_symbols,
        )

        self._scribbles: dict[Any, Any] = {}
        self._transaction_settings = TransactionSettings()
        self._unrealized_changes = RWLock(create_empty_unrealized_changes())
        self._asset_record = RWLock(create_empty_asset_record())
        self._auto_order_record = RWLock(
            pd.DataFrame(
                columns=["SYMBOL", "ORDER_ID"],
                index=pd.DatetimeIndex([], tz="UTC"),
            ),
        )

        self._account_listener = AccountListener(
            window=window,
            account_state=self._account_state,
            leverages=self._exchange_config.leverages,
            asset_record=self._asset_record,
            auto_order_record=self._auto_order_record,
        )

        state_config = StateConfig(
            account_state=self._account_state,
            transaction_settings=self._transaction_settings,
            unrealized_changes=self._unrealized_changes,
            asset_record=self._asset_record,
        )
        self._binance_watcher = BinanceWatcher(
            window=window,
            api_requester=self._api_requester,
            state_config=state_config,
            exchange_config=self._exchange_config,
        )

        order_placer_config = OrderPlacerConfig(
            account_state=self._account_state,
            auto_order_record=self._auto_order_record,
            aggregate_trades_queue=team.collector.aggregate_trades,
        )
        self._order_placer = OrderPlacer(
            window=window,
            api_requester=self._api_requester,
            config=order_placer_config,
            exchange_config=self._exchange_config,
        )

        self._scheduler.add_job(
            self._display_status_information,
            trigger="cron",
            second="*",
        )
        self._scheduler.add_job(
            self._display_range_information,
            trigger="cron",
            second="*",
        )
        self._scheduler.add_job(
            self._cancel_conflicting_orders,
            trigger="cron",
            second="*",
        )
        self._scheduler.add_job(
            self.display_lines,
            trigger="cron",
            second="*/10",
            kwargs={"periodic": True, "frequent": True},
        )
        self._scheduler.add_job(
            self._pan_view_range,
            trigger="cron",
            second="*/10",
        )
        self._scheduler.add_job(
            self._perform_transaction,
            trigger="cron",
            second="*/10",
        )
        self._scheduler.add_job(
            self._save_scribbles,
            trigger="cron",
            second="*/10",
        )
        self._scheduler.add_job(
            self.watch_binance,
            trigger="cron",
            second="*/10",
        )
        self._scheduler.add_job(
            self._organize_data,
            trigger="cron",
            minute="*",
        )
        self._scheduler.add_job(
            self._save_large_data,
            trigger="cron",
            hour="*",
        )
        self._scheduler.add_job(
            self.update_user_data_stream,
            trigger="cron",
            hour="*",
        )

        self.user_data_streamer: ApiStreamer | None = None

        when_internet_connected(self.watch_binance)
        when_internet_connected(self.update_user_data_stream)
        when_internet_disconnected(self.update_user_data_stream)

        self._connect_ui_events()

    def _connect_ui_events(self) -> None:
        window = self._window

        # Special widgets
        job = self._display_range_information
        outsource(window.transaction_graph.price_widget.sigRangeChanged, job)
        job = self._set_minimum_view_range
        outsource(window.transaction_graph.price_widget.sigRangeChanged, job)
        job = self._update_automation_settings
        outsource(window.comboBox_2.currentIndexChanged, job)
        job = self._update_automation_settings
        outsource(window.checkBox.toggled, job)
        job = self._update_keys
        outsource(window.lineEdit_4.editingFinished, job)
        job = self._update_keys
        outsource(window.lineEdit_6.editingFinished, job)
        job = self._toggle_frequent_draw
        outsource(window.checkBox_2.toggled, job)
        job = self.display_day_range
        outsource(window.pushButton_14.clicked, job)
        job = self._update_mode_settings
        outsource(window.spinBox.editingFinished, job)
        job = self._update_viewing_symbol
        outsource(window.comboBox_4.currentIndexChanged, job)

        action_menu = QMenu(window)
        window.pushButton_12.setMenu(action_menu)

        text = "Open Binance exchange"
        job = self._open_exchange
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Open Binance futures wallet"
        job = self._open_futures_wallet_page
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Open Binance API management webpage"
        job = self._open_api_management_page
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Clear all positions and open orders"
        job = self._clear_positions_and_open_orders
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Display same range as simulation graph"
        job = self._match_graph_range
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)
        text = "Show Raw Account State Object"
        job = self._show_raw_account_state_object
        new_action = action_menu.addAction(text)
        outsource(new_action.triggered, job)

    async def load_work(self) -> None:
        """Load transaction data from disk."""
        await aiofiles.os.makedirs(self._workerpath, exist_ok=True)

        # scribbles
        filepath = self._workerpath / "scribbles.pickle"
        if await aiofiles.os.path.isfile(filepath):
            async with aiofiles.open(filepath, "rb") as file:
                content = await file.read()
                self._scribbles = pickle.loads(content)

        # transaction settings
        filepath = self._workerpath / "transaction_settings.json"
        if await aiofiles.os.path.isfile(filepath):
            async with aiofiles.open(filepath, encoding="utf8") as file:
                read_data = TransactionSettings.model_validate_json(await file.read())
            self._transaction_settings = read_data
            state = read_data.should_transact
            self._window.checkBox.setChecked(state)
            strategy_index = read_data.strategy_index
            self._window.comboBox_2.setCurrentIndex(strategy_index)
            new_value = read_data.desired_leverage
            self._window.spinBox.setValue(new_value)
            text = read_data.binance_api_key
            self._window.lineEdit_4.setText(text)
            text = read_data.binance_api_secret
            self._window.lineEdit_6.setText(text)
            self._api_requester.update_keys(
                read_data.binance_api_key,
                read_data.binance_api_secret,
            )

        # unrealized changes
        filepath = self._workerpath / "unrealized_changes.pickle"
        if await aiofiles.os.path.isfile(filepath):
            sr: pd.Series = await spawn_blocking(pd.read_pickle, filepath)
            self._unrealized_changes = RWLock(sr)

        # asset record
        filepath = self._workerpath / "asset_record.pickle"
        if await aiofiles.os.path.isfile(filepath):
            df: pd.DataFrame = await spawn_blocking(pd.read_pickle, filepath)
            self._asset_record = RWLock(df)

        # auto order record
        filepath = self._workerpath / "auto_order_record.pickle"
        if await aiofiles.os.path.isfile(filepath):
            df: pd.DataFrame = await spawn_blocking(pd.read_pickle, filepath)
            self._auto_order_record = RWLock(df)

    async def dump_work(self) -> None:
        """Save transaction data to disk."""
        await self._save_large_data()
        await self._save_scribbles()

    async def _organize_data(self) -> None:
        async with self._unrealized_changes.write_lock as cell:
            if not cell.data.index.is_unique:
                unique_index = cell.data.index.drop_duplicates()
                cell.data = cell.data.reindex(unique_index)
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await spawn_blocking(sort_series, cell.data)

        async with self._auto_order_record.write_lock as cell:
            if not cell.data.index.is_unique:
                unique_index = cell.data.index.drop_duplicates()
                cell.data = cell.data.reindex(unique_index)
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await spawn_blocking(sort_data_frame, cell.data)
            max_length = 2**16
            if len(cell.data) > max_length:
                cell.data = cell.data.iloc[-max_length:].copy()

        async with self._asset_record.write_lock as cell:
            if not cell.data.index.is_unique:
                unique_index = cell.data.index.drop_duplicates()
                cell.data = cell.data.reindex(unique_index)
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await spawn_blocking(sort_data_frame, cell.data)

    async def _save_large_data(self) -> None:
        async with self._unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data.copy()
        await spawn_blocking(
            unrealized_changes.to_pickle,
            self._workerpath / "unrealized_changes.pickle",
        )

        async with self._auto_order_record.read_lock as cell:
            auto_order_record = cell.data.copy()
        await spawn_blocking(
            auto_order_record.to_pickle,
            self._workerpath / "auto_order_record.pickle",
        )

        async with self._asset_record.read_lock as cell:
            asset_record = cell.data.copy()
        await spawn_blocking(
            asset_record.to_pickle,
            self._workerpath / "asset_record.pickle",
        )

    async def _save_scribbles(self) -> None:
        filepath = self._workerpath / "scribbles.pickle"
        async with aiofiles.open(filepath, "wb") as file:
            content = pickle.dumps(self._scribbles)
            await file.write(content)

    async def update_user_data_stream(self) -> None:
        """Prepare WebSocket user data stream from Binance.

        Providing updates on account changes and market order results.

        Although rare, the listen key may change over time.
        Additionally, the Binance API documentation recommends
        extending the user data stream every hour.
        Thus, this function should be called periodically to maintain the stream.

        - https://binance-docs.github.io/apidocs/futures/en/#start-user-data-stream-user_stream
        """

        async def close_stream() -> None:
            if self.user_data_streamer:
                await self.user_data_streamer.close()
                self.user_data_streamer = None

        if not internet_connected():
            await close_stream()
            return

        try:
            response = await self._api_requester.binance(
                http_method="POST",
                path="/fapi/v1/listenKey",
            )
        except ApiRequestError:
            await close_stream()
            return

        listen_key = response["listenKey"]
        new_url = f"wss://fstream.binance.com/ws/{listen_key}"

        if self.user_data_streamer:
            if new_url == self.user_data_streamer.url:
                # If the listen key hasn't changed, do nothing.
                return
            # If the listen key has changed, close the previous session.
            await self.user_data_streamer.close()

        self.user_data_streamer = ApiStreamer(
            new_url,
            self._listen_to_account,
        )

    async def _listen_to_account(self, received: dict[str, Any]) -> None:
        await self._account_listener.handle_event(received)

        event_type = str(received["e"])
        if event_type == "listenKeyExpired":
            await self.update_user_data_stream()

        await self._cancel_conflicting_orders()

    async def _open_exchange(self) -> None:
        symbol = self._viewing_symbol
        await spawn_blocking(
            webbrowser.open,
            f"https://www.binance.com/en/futures/{symbol}",
        )

    async def _open_futures_wallet_page(self) -> None:
        await spawn_blocking(
            webbrowser.open,
            "https://www.binance.com/en/my/wallet/account/futures",
        )

    async def _open_api_management_page(self) -> None:
        await spawn_blocking(
            webbrowser.open,
            "https://www.binance.com/en/my/settings/api-management",
        )

    async def _save_transaction_settings(self) -> None:
        filepath = self._workerpath / "transaction_settings.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            await file.write(self._transaction_settings.model_dump_json(indent=2))

    async def _update_keys(self) -> None:
        binance_api_key = self._window.lineEdit_4.text()
        binance_api_secret = self._window.lineEdit_6.text()

        self._transaction_settings.binance_api_key = binance_api_key
        self._transaction_settings.binance_api_secret = binance_api_secret

        await self._save_transaction_settings()
        self._api_requester.update_keys(binance_api_key, binance_api_secret)
        await self.update_user_data_stream()

    async def _update_automation_settings(self) -> None:
        strategy_index = self._window.comboBox_2.currentIndex()
        self._transaction_settings.strategy_index = strategy_index

        spawn(self.display_lines())

        is_checked = self._window.checkBox.isChecked()

        if is_checked:
            self._transaction_settings.should_transact = True
        else:
            self._transaction_settings.should_transact = False

        await self._save_transaction_settings()

    async def _display_range_information(self) -> None:
        self._range_display_task.spawn(self._display_range_information_real())

    def _calculate_trade_metrics(
        self,
        asset_record: pd.DataFrame,
        asset_changes: pd.Series,
        symbol_mask: pd.Series,
    ) -> TradeMetrics:
        """Calculate trade counts, margins, and yields."""
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

        return TradeMetrics(
            total_change_count=total_change_count,
            symbol_change_count=symbol_change_count,
            total_margin_ratio=total_margin_ratio,
            symbol_margin_ratio=symbol_margin_ratio,
            total_yield=total_yield,
            symbol_yield=symbol_yield,
        )

    async def _display_range_information_real(self) -> None:
        symbol = self._viewing_symbol
        price_widget = self._window.transaction_graph.price_widget

        range_start_timestamp = max(price_widget.getAxis("bottom").range[0], 0.0)
        range_start = datetime.fromtimestamp(range_start_timestamp, tz=UTC)

        range_end_timestamp = price_widget.getAxis("bottom").range[1]
        if range_end_timestamp < 0.0:
            range_end_timestamp = 9223339636.0
        else:
            range_end_timestamp = min(range_end_timestamp, 9223339636.0)
        range_end = datetime.fromtimestamp(range_end_timestamp, tz=UTC)

        range_length = range_end - range_start
        range_days = range_length.days
        range_hours, range_minutes, _ = (
            range_length.seconds // 3600,
            (range_length.seconds % 3600) // 60,
            range_length.seconds % 60,
        )

        async with self._unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data[range_start:range_end].copy()
        async with self._asset_record.read_lock as cell:
            asset_record = cell.data[range_start:range_end].copy()

        auto_trade_mask = asset_record["CAUSE"] == "AUTO_TRADE"
        asset_changes = asset_record["RESULT_ASSET"].pct_change(fill_method=None) + 1
        asset_record = asset_record[auto_trade_mask]
        asset_changes = asset_changes.reindex(asset_record.index, fill_value=1.0)
        symbol_mask = asset_record["SYMBOL"] == symbol

        metrics = self._calculate_trade_metrics(
            asset_record,
            asset_changes,
            symbol_mask,
        )

        min_unrealized_change = (
            unrealized_changes.min() if len(unrealized_changes) > 0 else 0
        )

        price_widget = self._window.transaction_graph.price_widget
        view_range = price_widget.getAxis("left").range
        price_range_height = (1 - view_range[0] / view_range[1]) * 100

        text = ""
        text += f"Visible time range {range_days}d {range_hours}h {range_minutes}s"
        text += "  ⦁  "
        text += "Visible price range"
        text += f" {price_range_height:.2f}%"
        text += "  ⦁  "
        text += f"Transaction count {metrics.symbol_change_count}"
        text += f"({metrics.total_change_count})"
        text += "  ⦁  "
        text += "Transaction amount"
        text += f" *{metrics.symbol_margin_ratio:.4f}"
        text += f"({metrics.total_margin_ratio:.4f})"
        text += "  ⦁  "
        text += f"Total realized profit {metrics.symbol_yield:+.4f}"
        text += f"({metrics.total_yield:+.4f})%"
        text += "  ⦁  "
        text += "Lowest unrealized profit"
        text += f" {min_unrealized_change * 100:+.4f}%"
        self._window.label_8.setText(text)

    async def _set_minimum_view_range(self) -> None:
        widget = self._window.transaction_graph.price_widget
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore
        widget = self._window.transaction_graph.asset_widget
        range_down = widget.getAxis("left").range[0]
        widget.plotItem.vb.setLimits(minYRange=range_down * 0.005)  # type:ignore

    async def display_strategy_index(self) -> None:
        """Update UI with current strategy selection."""
        strategy_index = self._transaction_settings.strategy_index
        self._window.comboBox_2.setCurrentIndex(strategy_index)

    async def display_lines(
        self,
        periodic: bool = False,
        frequent: bool = False,
    ) -> None:
        """Update transaction graph lines."""
        self._line_display_task.spawn(self._display_lines_real(periodic, frequent))

    def _get_transaction_time_range(self) -> DisplayTimeRange:
        """Calculate time range for transaction display."""
        if self._should_draw_frequently:
            get_from = datetime.now(UTC) - timedelta(days=28)
            slice_from = datetime.now(UTC) - timedelta(hours=24)
            slice_until = datetime.now(UTC)
        else:
            current_year = datetime.now(UTC).year
            get_from = datetime(current_year, 1, 1, tzinfo=UTC)
            slice_from = datetime(current_year, 1, 1, tzinfo=UTC)
            slice_until = datetime.now(UTC)
        slice_until -= timedelta(seconds=1)
        return DisplayTimeRange(
            get_from=get_from,
            slice_from=slice_from,
            slice_until=slice_until,
        )

    def _collect_realtime_data(self, symbol: str) -> RealtimeData:
        """Collect and filter realtime market data."""
        realtime_data = slice_deque(team.collector.realtime_data, 2 ** (10 + 6))
        mark_prices: list[Any] = []
        book_tickers: list[Any] = []
        for realtime_record in realtime_data:
            if isinstance(realtime_record, BookTicker):
                if realtime_record.symbol == symbol:
                    book_tickers.append(realtime_record)
            else:
                is_valid = realtime_record.mark_price > 0.0
                if is_valid and realtime_record.symbol == symbol:
                    mark_prices.append(realtime_record)

        aggregate_trades = slice_deque(team.collector.aggregate_trades, 2 ** (10 + 6))
        aggregate_trades = [a for a in aggregate_trades if a.symbol == symbol]

        return RealtimeData(
            mark_prices=mark_prices,
            book_tickers=book_tickers,
            aggregate_trades=aggregate_trades,
        )

    async def _load_transaction_asset_data(
        self,
        symbol: str,
        time_range: DisplayTimeRange,
    ) -> TransactionAssetData:
        """Load candle and asset data for transaction display."""
        async with team.collector.candle_data.read_lock as cell:
            columns = [str(s) for s in cell.data.columns]
            chosen_columns = [s for s in columns if s.startswith(symbol)]
            candle_data_original = cell.data[chosen_columns][
                time_range.get_from : time_range.slice_until
            ].copy()

        async with self._asset_record.read_lock as cell:
            if len(cell.data) > 0:
                last_asset = cell.data.iloc[-1]["RESULT_ASSET"]
            else:
                last_asset = None
            before_record = cell.data[: time_range.slice_from]
            if len(before_record) > 0:
                before_asset = before_record.iloc[-1]["RESULT_ASSET"]
            else:
                before_asset = None
            asset_record = cell.data[time_range.slice_from :].copy()

        candle_data = candle_data_original[time_range.slice_from :]

        if len(candle_data) > 0:
            last_written_moment = candle_data.index[-1]
            new_moment = last_written_moment + timedelta(seconds=10)
            new_index = candle_data.index.union([new_moment])
            candle_data = candle_data.reindex(new_index)

        return TransactionAssetData(
            candle_original=candle_data_original,
            candle_sliced=candle_data,
            asset_record=asset_record,
            last_asset=last_asset,
            before_asset=before_asset,
        )

    async def _update_transaction_asset_record(
        self,
        asset_record: pd.DataFrame,
        last_asset: float | None,
        before_asset: float | None,
        slice_from: datetime,
    ) -> pd.DataFrame:
        """Update asset record with latest observations."""
        if last_asset is not None:
            observed_until = self._account_state.observed_until
            if (
                len(asset_record) == 0 or asset_record.index[-1] < observed_until
            ) and slice_from < observed_until:
                asset_record.loc[observed_until, "CAUSE"] = "OTHER"
                asset_record.loc[observed_until, "RESULT_ASSET"] = last_asset
                if not asset_record.index.is_monotonic_increasing:
                    asset_record = await spawn_blocking(
                        sort_data_frame,
                        asset_record,
                    )

        if before_asset is not None:
            asset_record.loc[slice_from, "CAUSE"] = "OTHER"
            asset_record.loc[slice_from, "RESULT_ASSET"] = before_asset
            if not asset_record.index.is_monotonic_increasing:
                asset_record = await spawn_blocking(sort_data_frame, asset_record)

        return asset_record

    async def _display_lines_real(self, periodic: bool, frequent: bool) -> None:
        symbol = self._viewing_symbol
        strategy_index = self._transaction_settings.strategy_index
        strategy = team.strategist.strategies[strategy_index]

        if frequent and not self._should_draw_frequently:
            return

        async with team.collector.candle_data.read_lock as cell:
            if len(cell.data) == 0:
                return

        if periodic:
            current_moment = to_moment(datetime.now(UTC))
            before_moment = current_moment - timedelta(seconds=10)
            for _ in range(50):
                async with team.collector.candle_data.read_lock as cell:
                    if cell.data.index[-1] == before_moment:
                        break
                await sleep(0.1)

        duration_recorder = DurationRecorder("DISPLAY_TRANSACTION_LINES")

        time_range = self._get_transaction_time_range()
        realtime_data = self._collect_realtime_data(symbol)

        position = self._account_state.positions[symbol]
        entry_price = (
            None
            if position.direction == PositionDirection.NONE
            else position.entry_price
        )

        await self._window.transaction_graph.update_light_lines(
            mark_prices=realtime_data.mark_prices,
            aggregate_trades=realtime_data.aggregate_trades,
            book_tickers=realtime_data.book_tickers,
            entry_price=entry_price,
            observed_until=self._account_state.observed_until,
        )

        async with self._unrealized_changes.read_lock as cell:
            unrealized_changes = cell.data.copy()

        asset_data = await self._load_transaction_asset_data(symbol, time_range)

        asset_record = await self._update_transaction_asset_record(
            asset_data.asset_record,
            asset_data.last_asset,
            asset_data.before_asset,
            time_range.slice_from,
        )

        await self._window.transaction_graph.update_heavy_lines(
            symbol=symbol,
            candle_data=asset_data.candle_sliced,
            asset_record=asset_record,
            unrealized_changes=unrealized_changes,
        )

        indicators = await spawn_blocking(
            make_indicators,
            strategy=strategy,
            target_symbols=[self._viewing_symbol],
            candle_data=asset_data.candle_original,
        )
        indicators = indicators[time_range.slice_from : time_range.slice_until]

        await self._window.transaction_graph.update_custom_lines(symbol, indicators)
        duration_recorder.record()
        await self._set_minimum_view_range()

    async def _toggle_frequent_draw(self) -> None:
        is_checked = self._window.checkBox_2.isChecked()
        if is_checked:
            self._should_draw_frequently = True
        else:
            self._should_draw_frequently = False
        await self.display_lines()

    async def _update_viewing_symbol(self) -> None:
        alias = self._window.comboBox_4.currentText()
        symbol = self._window.alias_to_symbol[alias]
        self._viewing_symbol = symbol

        spawn(self.display_lines())
        spawn(self._display_status_information())
        spawn(self._display_range_information())

    async def _display_status_information(self) -> None:
        time_passed = datetime.now(UTC) - self._account_state.observed_until
        if time_passed > timedelta(seconds=30):
            text = (
                "Couldn't get the latest info on your Binance account due to a problem"
                " with your key or connection to the Binance server."
            )
            self._window.label_16.setText(text)
            return

        if not self._is_key_restrictions_satisfied:
            text = (
                "API key's restrictions are not satisfied. Auto transaction is"
                " disabled. Go to your Binance API managements webpage to change"
                " the restrictions."
            )
            self._window.label_16.setText(text)
            return

        cumulation_rate = await team.collector.check_candle_data_cumulation_rate()
        if cumulation_rate < 1:
            text = (
                "For auto transaction to work, the past 24 hour accumulation rate of"
                " candle data must be 100%. Auto transaction is disabled."
            )
            self._window.label_16.setText(text)
            return

        position = self._account_state.positions[self._viewing_symbol]
        if position.direction == PositionDirection.LONG:
            direction_text = "long"
        elif position.direction == PositionDirection.SHORT:
            direction_text = "short"
        else:
            direction_text = "none"
        margin_sum = 0
        for each_position in self._account_state.positions.values():
            margin_sum += each_position.margin

        open_orders = self._account_state.open_orders
        open_orders_count = len(open_orders[self._viewing_symbol])
        all_open_orders_count = 0
        for symbol_open_orders in open_orders.values():
            all_open_orders_count += len(symbol_open_orders)

        text = ""
        text += "Total asset"
        text += f" ${self._account_state.wallet_balance:.4f}"
        text += "  ⦁  "
        text += f"Investment ${position.margin:.4f}"
        text += f"({margin_sum:.4f})"
        text += "  ⦁  "
        text += f"Direction {direction_text}"
        text += "  ⦁  "
        text += "Entry price"
        text += f" ${position.entry_price:.4f}"
        text += "  ⦁  "
        text += "Open orders"
        text += f" {open_orders_count}"
        text += f"({all_open_orders_count})"

        self._window.label_16.setText(text)

    async def _calculate_indicators(
        self,
        candle_data: pd.DataFrame,
        all_columns: pd.Index,
        target_symbols: list[str],
        strategy: Strategy,
    ) -> IndicatorData:
        """Calculate indicators and extract current values."""
        columns = [str(s) for s in all_columns]
        coroutines: list[Coroutine[Any, Any, pd.DataFrame]] = []
        for symbol in target_symbols:
            chosen_columns = [s for s in columns if s.startswith(symbol)]
            coroutines.append(
                spawn_blocking(
                    make_indicators,
                    strategy=strategy,
                    target_symbols=[symbol],
                    candle_data=candle_data[chosen_columns],
                ),
            )
            await sleep(0.0)
        symbol_indicators = await gather(*coroutines)
        indicators = pd.concat(symbol_indicators, axis="columns")

        record_row: np.record = candle_data.tail(1).to_records()[-1]
        current_candle_data = {
            k: float(record_row[k])
            for k in record_row.dtype.names or ()
            if k != "index"
        }
        record_row: np.record = indicators.to_records()[-1]
        current_indicators = {
            k: float(record_row[k])
            for k in record_row.dtype.names or ()
            if k != "index"
        }
        return IndicatorData(
            current_candle_data=current_candle_data,
            current_indicators=current_indicators,
        )

    async def _perform_transaction(self) -> None:
        self._window.progressBar_2.setValue(0)

        if not internet_connected():
            return

        if not self._transaction_settings.should_transact:
            return

        if not self._is_key_restrictions_satisfied:
            return

        cumulation_rate = await team.collector.check_candle_data_cumulation_rate()
        if cumulation_rate < 1:
            return

        duration_recorder = DurationRecorder("PERFORM_TRANSACTION")
        current_moment = to_moment(datetime.now(UTC))
        before_moment = current_moment - timedelta(seconds=10)

        is_cycle_done = False

        async def play_progress_bar() -> None:
            passed_time = timedelta(seconds=0)
            while passed_time < timedelta(seconds=10):
                passed_time = datetime.now(UTC) - current_moment
                if not is_cycle_done:
                    new_value = int(passed_time / timedelta(seconds=10) * 1000)
                else:
                    before_value = self._window.progressBar_2.value()
                    remaining = 1000 - before_value
                    new_value = before_value + math.ceil(remaining * 0.2)
                self._window.progressBar_2.setValue(new_value)
                await sleep(0.01)

        spawn(play_progress_bar())

        async with team.collector.candle_data.read_lock as cell:
            if len(cell.data) == 0:
                # case when the app is executed for the first time
                return

        for _ in range(50):
            async with team.collector.candle_data.read_lock as cell:
                last_index = cell.data.index[-1]
                if last_index == before_moment:
                    break
            await sleep(0.1)

        slice_from = datetime.now(UTC) - timedelta(days=28)
        async with team.collector.candle_data.read_lock as cell:
            candle_data = cell.data[slice_from:].copy()

        target_symbols = self._window.data_settings.target_symbols
        strategy_index = self._transaction_settings.strategy_index
        strategy = team.strategist.strategies[strategy_index]

        indicator_data = await self._calculate_indicators(
            candle_data,
            cell.data.columns,
            target_symbols,
            strategy,
        )

        decision_context = DecisionContext(
            strategy=strategy,
            target_symbols=target_symbols,
            current_moment=current_moment,
            current_candle_data=indicator_data.current_candle_data,
            current_indicators=indicator_data.current_indicators,
            account_state=self._account_state,
            scribbles=self._scribbles,
        )
        decisions = make_decisions(decision_context)

        is_cycle_done = True
        duration_recorder.record()

        await self.place_orders(decisions)

    async def display_day_range(self) -> None:
        """Display 24-hour time range."""
        range_start = (datetime.now(UTC) - timedelta(hours=24)).timestamp()
        range_end = datetime.now(UTC).timestamp()
        widget = self._window.transaction_graph.price_widget
        widget.setXRange(range_start, range_end)

    async def _match_graph_range(self) -> None:
        graph_from = self._window.simulation_graph.price_widget
        graph_to = self._window.transaction_graph.price_widget
        graph_range = graph_from.getAxis("bottom").range
        range_start = graph_range[0]
        range_end = graph_range[1]
        graph_to.setXRange(range_start, range_end, padding=0)  # type:ignore

    async def _update_mode_settings(self) -> None:
        desired_leverage = self._window.spinBox.value()
        self._transaction_settings.desired_leverage = desired_leverage

        target_symbols = self._window.data_settings.target_symbols
        target_max_leverages: dict[str, int] = {}
        for symbol in target_symbols:
            max_leverage = self._exchange_config.maximum_leverages.get(symbol, 125)
            target_max_leverages[symbol] = max_leverage
        lowest_max_leverage = min(target_max_leverages.values())

        if lowest_max_leverage < desired_leverage:
            answer = await ask(
                "Leverage on some symbols cannot be set as desired",
                "Binance has its own leverage limit per market. For some symbols,"
                " leverage will be set as high as it can be, but not as same as the"
                " value entered. Generally, situation gets safer in terms of lowest"
                " unrealized changes and profit turns out to be a bit lower than"
                " simulation prediction with the same leverage.",
                ["Show details", "Okay"],
            )
            if answer == 1:
                texts: list[str] = []
                for symbol, max_leverage in target_max_leverages.items():
                    texts.append(f"{symbol} {max_leverage}")
                text = "\n".join(texts)
                await ask(
                    "These are highest available leverages",
                    text,
                    ["Okay"],
                )

        await self._save_transaction_settings()

    async def watch_binance(self) -> None:
        """Watch Binance for account updates."""
        await self._binance_watcher.watch(self.place_orders)
        self._is_key_restrictions_satisfied = (
            self._binance_watcher.is_key_restrictions_satisfied
        )

    async def place_orders(
        self,
        decisions: dict[str, dict[OrderType, Decision]],
    ) -> None:
        """Place orders based on strategy decisions."""
        await self._order_placer.place(decisions)

    async def _clear_positions_and_open_orders(self) -> None:
        decisions: dict[str, dict[OrderType, Decision]] = {}
        for symbol in self._window.data_settings.target_symbols:
            decisions[symbol] = {
                OrderType.CANCEL_ALL: Decision(),
                OrderType.NOW_CLOSE: Decision(),
            }
        await self.place_orders(decisions)

    async def _cancel_conflicting_orders(self) -> None:
        if not self._transaction_settings.should_transact:
            return

        conflicting_order_tuples: list[tuple[str, int]] = []
        for symbol in self._window.data_settings.target_symbols:
            symbol_open_orders = self._account_state.open_orders[symbol]
            grouped_open_orders: dict[OrderType, list[int]] = {}
            for order_id, open_order_state in symbol_open_orders.items():
                order_type = open_order_state.order_type
                if order_type not in grouped_open_orders:
                    grouped_open_orders[order_type] = [order_id]
                else:
                    grouped_open_orders[order_type].append(order_id)
            for order_type, group in grouped_open_orders.items():
                if order_type == OrderType.OTHER:
                    conflicting_order_tuples.extend(
                        (symbol, order_id) for order_id in group
                    )
                elif len(group) > 1:
                    latest_id = max(group)
                    conflicting_order_tuples.extend(
                        (symbol, order_id)
                        for order_id in group
                        if order_id != latest_id
                    )

        async def job(conflicting_order_tuple: tuple[str, int]) -> None:
            try:
                payload = {
                    "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                    "symbol": conflicting_order_tuple[0],
                    "orderId": conflicting_order_tuple[1],
                }
                await self._api_requester.binance(
                    http_method="DELETE",
                    path="/fapi/v1/order",
                    payload=payload,
                )
            except ApiRequestError:
                pass

        if conflicting_order_tuples:
            await gather(*(job(c) for c in conflicting_order_tuples))

    async def _pan_view_range(self) -> None:
        if not self._should_draw_frequently:
            return

        widget = self._window.transaction_graph.price_widget
        before_range = widget.getAxis("bottom").range
        range_start = before_range[0]
        range_end = before_range[1]

        if range_end - range_start < 6 * 60 * 60:  # six hours
            return

        widget.setXRange(range_start + 10, range_end + 10, padding=0)  # type:ignore

    async def _show_raw_account_state_object(self) -> None:
        text = ""

        now_time = datetime.now(UTC)
        time_text = now_time.strftime("%Y-%m-%d %H:%M:%S")
        text += f"At UTC {time_text}"

        text += "\n\n"
        text += self._account_state.model_dump_json(indent=2)

        await overlay(LongTextView(text))
