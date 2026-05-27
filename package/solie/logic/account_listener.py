"""Account event listener for Binance user data stream."""

from datetime import UTC, datetime
from logging import getLogger
from typing import Any, NamedTuple

import polars as pl
from polars import DataFrame

from solie.common import spawn_blocking
from solie.utility import (
    ASSET_RECORD_SCHEMA,
    AccountState,
    OpenOrder,
    OrderType,
    PositionDirection,
    RWLock,
    list_to_dict,
    sort_data_frame,
)
from solie.window import Window

logger = getLogger(__name__)


class OrderParseResult(NamedTuple):
    """Parsed order information from Binance event."""

    order_type: OrderType
    boundary: float
    left_margin: float | None


class TradeExecutionInfo(NamedTuple):
    """Trade execution details from Binance."""

    symbol: str
    order_id: int
    side: str
    is_maker: bool
    last_filled_price: float
    last_filled_quantity: float
    realized_profit: float
    commission: float
    leverage: int
    wallet_balance: float
    event_time: datetime


class UpdateTradeRecordInfo(NamedTuple):
    """Information for updating existing trade record."""

    data: DataFrame
    symbol_df: DataFrame
    order_id: int
    added_margin_ratio: float
    added_revenue: float
    last_timestamp: int


class CreateTradeRecordInfo(NamedTuple):
    """Information for creating new trade record."""

    data: DataFrame
    symbol: str
    order_id: int
    side: str
    is_maker: bool
    last_filled_price: float
    added_margin_ratio: float
    added_revenue: float
    unique_order_ids: set[int]
    event_time: datetime
    last_timestamp: int


class ParseOrderTypeParams(NamedTuple):
    """Parameters for parsing order type from Binance data."""

    order_type: str
    side: str
    close_position: bool
    price: float
    stop_price: float
    origianal_quantity: float
    executed_quantity: float
    leverage: int


class AccountListener:
    """Handles Binance account update events."""

    def __init__(
        self,
        window: Window,
        account_state: AccountState,
        leverages: dict[str, int],
        asset_record: RWLock[DataFrame],
        auto_order_record: RWLock[DataFrame],
    ) -> None:
        """Initialize account listener."""
        self._window = window
        self._account_state = account_state
        self._leverages = leverages
        self._asset_record = asset_record
        self._auto_order_record = auto_order_record

    async def handle_event(self, received: dict[str, Any]) -> None:
        """Process account update events from Binance."""
        event_type = str(received["e"])
        event_timestamp = int(received["E"]) / 1000
        event_time = datetime.fromtimestamp(event_timestamp, tz=UTC)

        self._account_state.observed_until = event_time

        if event_type == "listenKeyExpired":
            logger.warning("Binance user data stream listen key has expired")
            return

        if event_type == "ACCOUNT_UPDATE":
            await self._handle_account_update(received, event_time)

        elif event_type == "ORDER_TRADE_UPDATE":
            await self._handle_order_trade_update(received, event_time)

    async def _handle_account_update(
        self,
        received: dict[str, Any],
        event_time: datetime,
    ) -> None:
        """Handle ACCOUNT_UPDATE event."""
        about_update = received["a"]
        about_assets = about_update["B"]
        about_positions = about_update["P"]

        asset_token = self._window.data_settings.asset_token

        about_assets_keyed = list_to_dict(about_assets, "a")
        about_asset = about_assets_keyed[asset_token]
        wallet_balance = float(about_asset["wb"])
        self._account_state.wallet_balance = wallet_balance

        about_positions_keyed = list_to_dict(about_positions, "ps")
        if "BOTH" not in about_positions_keyed:
            return

        about_position = about_positions_keyed["BOTH"]

        target_symbols = self._window.data_settings.target_symbols
        if about_position["s"] not in target_symbols:
            return

        symbol = str(about_position["s"])
        amount = float(about_position["pa"])
        entry_price = float(about_position["ep"])

        leverage = self._leverages[symbol]
        margin = abs(amount) * entry_price / leverage
        if amount < 0.0:
            direction = PositionDirection.SHORT
        elif amount > 0.0:
            direction = PositionDirection.LONG
        else:
            direction = PositionDirection.LONG

        position = self._account_state.positions[symbol]
        position.margin = margin
        position.direction = direction
        position.entry_price = entry_price
        position.update_time = event_time

    async def _handle_order_trade_update(
        self,
        received: dict[str, Any],
        event_time: datetime,
    ) -> None:
        """Handle ORDER_TRADE_UPDATE event."""
        about_update = received["o"]

        target_symbols = self._window.data_settings.target_symbols
        if about_update["s"] not in target_symbols:
            return

        symbol = str(about_update["s"])
        order_id = int(about_update["i"])
        order_type = str(about_update["o"])
        order_status = str(about_update["X"])
        execution_type = str(about_update["x"])

        side = str(about_update["S"])
        close_position = bool(about_update["cp"])
        is_maker = bool(about_update["m"])

        origianal_quantity = float(about_update["q"])
        executed_quantity = float(about_update["z"])
        last_filled_quantity = float(about_update["l"])
        last_filled_price = float(about_update["L"])
        price = float(about_update["p"])
        stop_price = float(about_update["sp"])
        commission = float(about_update["n"])
        realized_profit = float(about_update["rp"])

        leverage = self._leverages[symbol]
        wallet_balance = self._account_state.wallet_balance

        # Remove order if no longer active
        if (
            order_status not in ("NEW", "PARTIALLY_FILLED")
            and order_id in self._account_state.open_orders[symbol]
        ):
            self._account_state.open_orders[symbol].pop(order_id)

        # Update or create order
        if order_status in ("NEW", "PARTIALLY_FILLED"):
            params = ParseOrderTypeParams(
                order_type=order_type,
                side=side,
                close_position=close_position,
                price=price,
                stop_price=stop_price,
                origianal_quantity=origianal_quantity,
                executed_quantity=executed_quantity,
                leverage=leverage,
            )
            parsed_order = self.parse_order_type(params)
            if parsed_order:
                self._account_state.open_orders[symbol][order_id] = OpenOrder(
                    order_type=parsed_order.order_type,
                    boundary=parsed_order.boundary,
                    left_margin=parsed_order.left_margin,
                )

        # Record trade execution
        if execution_type == "TRADE":
            trade_info = TradeExecutionInfo(
                symbol=symbol,
                order_id=order_id,
                side=side,
                is_maker=is_maker,
                last_filled_price=last_filled_price,
                last_filled_quantity=last_filled_quantity,
                realized_profit=realized_profit,
                commission=commission,
                leverage=leverage,
                wallet_balance=wallet_balance,
                event_time=event_time,
            )
            await self._record_trade_execution(trade_info)

    def parse_order_type(
        self,
        params: ParseOrderTypeParams,
    ) -> OrderParseResult | None:
        """Parse order type and calculate boundary and left margin."""
        if params.order_type == "STOP_MARKET":
            return self._parse_stop_market(
                params.side,
                params.close_position,
                params.stop_price,
                params.origianal_quantity,
                params.leverage,
            )
        if params.order_type == "TAKE_PROFIT_MARKET":
            return self._parse_take_profit_market(
                params.side,
                params.close_position,
                params.stop_price,
                params.origianal_quantity,
                params.leverage,
            )
        if params.order_type == "LIMIT":
            return self._parse_limit_order(
                params.side,
                params.price,
                params.origianal_quantity,
                params.executed_quantity,
                params.leverage,
            )
        # Other order types
        boundary = max(params.price, params.stop_price)
        left_quantity = params.origianal_quantity - params.executed_quantity
        left_margin = left_quantity * boundary / params.leverage
        return OrderParseResult(OrderType.OTHER, boundary, left_margin)

    def _parse_stop_market(
        self,
        side: str,
        close_position: bool,
        stop_price: float,
        origianal_quantity: float,
        leverage: int,
    ) -> OrderParseResult:
        """Parse STOP_MARKET order."""
        if close_position:
            if side == "BUY":
                return OrderParseResult(OrderType.LATER_UP_CLOSE, stop_price, None)
            if side == "SELL":
                return OrderParseResult(OrderType.LATER_DOWN_CLOSE, stop_price, None)
            msg = "Cannot order with this side"
            raise ValueError(msg)
        if side == "BUY":
            left_margin = origianal_quantity * stop_price / leverage
            return OrderParseResult(OrderType.LATER_UP_BUY, stop_price, left_margin)
        if side == "SELL":
            left_margin = origianal_quantity * stop_price / leverage
            return OrderParseResult(OrderType.LATER_DOWN_SELL, stop_price, left_margin)
        msg = "Cannot order with this side"
        raise ValueError(msg)

    def _parse_take_profit_market(
        self,
        side: str,
        close_position: bool,
        stop_price: float,
        origianal_quantity: float,
        leverage: int,
    ) -> OrderParseResult:
        """Parse TAKE_PROFIT_MARKET order."""
        if close_position:
            if side == "BUY":
                return OrderParseResult(OrderType.LATER_DOWN_CLOSE, stop_price, None)
            if side == "SELL":
                return OrderParseResult(OrderType.LATER_UP_CLOSE, stop_price, None)
            msg = "Cannot order with this side"
            raise ValueError(msg)
        if side == "BUY":
            left_margin = origianal_quantity * stop_price / leverage
            return OrderParseResult(OrderType.LATER_DOWN_BUY, stop_price, left_margin)
        if side == "SELL":
            left_margin = origianal_quantity * stop_price / leverage
            return OrderParseResult(OrderType.LATER_UP_SELL, stop_price, left_margin)
        msg = "Cannot order with this side"
        raise ValueError(msg)

    def _parse_limit_order(
        self,
        side: str,
        price: float,
        origianal_quantity: float,
        executed_quantity: float,
        leverage: int,
    ) -> OrderParseResult:
        """Parse LIMIT order."""
        left_quantity = origianal_quantity - executed_quantity
        left_margin = left_quantity * price / leverage
        if side == "BUY":
            return OrderParseResult(OrderType.BOOK_BUY, price, left_margin)
        if side == "SELL":
            return OrderParseResult(OrderType.BOOK_SELL, price, left_margin)
        msg = "Cannot order with this side"
        raise ValueError(msg)

    async def _record_trade_execution(
        self,
        info: TradeExecutionInfo,
    ) -> None:
        """Record trade execution in asset record."""
        added_revenue = info.realized_profit - info.commission
        added_notional = info.last_filled_price * info.last_filled_quantity
        added_margin = added_notional / info.leverage
        added_margin_ratio = added_margin / info.wallet_balance

        async with self._auto_order_record.read_lock as cell:
            symbol_df = cell.data.filter(pl.col("SYMBOL") == info.symbol)
            unique_order_ids = {int(i) for i in symbol_df["ORDER_ID"].unique()}

        async with self._asset_record.write_lock as cell:
            symbol_df = cell.data.filter(pl.col("SYMBOL") == info.symbol)
            recorded_id_list = symbol_df["ORDER_ID"].to_list()
            does_record_exist = info.order_id in recorded_id_list
            last_timestamp = (
                int(cell.data["timestamp"][-1]) if len(cell.data) > 0 else 0
            )

            if does_record_exist:
                cell.data = await self._update_existing_trade_record(
                    UpdateTradeRecordInfo(
                        data=cell.data,
                        symbol_df=symbol_df,
                        order_id=info.order_id,
                        added_margin_ratio=added_margin_ratio,
                        added_revenue=added_revenue,
                        last_timestamp=last_timestamp,
                    ),
                )
            else:
                cell.data = await self._create_new_trade_record(
                    CreateTradeRecordInfo(
                        data=cell.data,
                        symbol=info.symbol,
                        order_id=info.order_id,
                        side=info.side,
                        is_maker=info.is_maker,
                        last_filled_price=info.last_filled_price,
                        added_margin_ratio=added_margin_ratio,
                        added_revenue=added_revenue,
                        unique_order_ids=unique_order_ids,
                        event_time=info.event_time,
                        last_timestamp=last_timestamp,
                    ),
                )
            cell.data = await spawn_blocking(
                sort_data_frame,
                cell.data,
            )

    async def _update_existing_trade_record(
        self,
        info: UpdateTradeRecordInfo,
    ) -> DataFrame:
        """Update existing trade record."""
        mask_sr = info.symbol_df["ORDER_ID"] == info.order_id
        matching_rows = info.symbol_df.filter(mask_sr)
        if len(matching_rows) == 0:
            return info.data
        rec_timestamp = int(matching_rows["timestamp"][0])
        rec_value = float(matching_rows["MARGIN_RATIO"][0])
        last_rows = info.data.filter(pl.col("timestamp") == info.last_timestamp)
        if len(last_rows) == 0:
            return info.data
        last_asset = float(last_rows["RESULT_ASSET"][0])
        return info.data.with_columns(
            MARGIN_RATIO=pl.when(pl.col("timestamp") == rec_timestamp)
            .then(pl.lit(rec_value + info.added_margin_ratio))
            .otherwise(pl.col("MARGIN_RATIO")),
            RESULT_ASSET=pl.when(pl.col("timestamp") == info.last_timestamp)
            .then(pl.lit(last_asset + info.added_revenue))
            .otherwise(pl.col("RESULT_ASSET")),
        )

    async def _create_new_trade_record(
        self,
        info: CreateTradeRecordInfo,
    ) -> DataFrame:
        """Create new trade record."""
        record_timestamp = int(info.event_time.timestamp() * 1000)
        existing_timestamps = set(info.data["timestamp"].to_list())
        while record_timestamp in existing_timestamps:
            record_timestamp += 1

        last_rows = info.data.filter(pl.col("timestamp") == info.last_timestamp)
        last_asset = float(last_rows["RESULT_ASSET"][0]) if len(last_rows) > 0 else 0.0
        new_value = last_asset + info.added_revenue

        if info.order_id in info.unique_order_ids:
            cause = "AUTO_TRADE"
        else:
            cause = "MANUAL_TRADE"
        return pl.concat(
            [
                info.data,
                DataFrame(
                    [
                        {
                            "timestamp": record_timestamp,
                            "CAUSE": cause,
                            "SYMBOL": info.symbol,
                            "SIDE": "SELL" if info.side == "SELL" else "BUY",
                            "FILL_PRICE": info.last_filled_price,
                            "ROLE": "MAKER" if info.is_maker else "TAKER",
                            "MARGIN_RATIO": info.added_margin_ratio,
                            "ORDER_ID": info.order_id,
                            "RESULT_ASSET": new_value,
                        },
                    ],
                    schema=ASSET_RECORD_SCHEMA,
                ),
            ],
        )
