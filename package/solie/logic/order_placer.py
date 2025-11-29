"""Order placer for Binance futures trading."""

from asyncio import gather
from collections import deque
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Any, ClassVar, NamedTuple

import pandas as pd

from solie.common import spawn_blocking
from solie.utility import (
    AccountState,
    AggregateTrade,
    ApiRequester,
    Decision,
    OrderType,
    PositionDirection,
    RWLock,
    ball_ceil,
    slice_deque,
    sort_data_frame,
    to_moment,
)
from solie.window import Window

from .binance_watcher import ExchangeConfig

logger = getLogger(__name__)


class OrderPlacerConfig(NamedTuple):
    """Configuration for OrderPlacer."""

    account_state: AccountState
    auto_order_record: RWLock[pd.DataFrame]
    aggregate_trades_queue: deque[AggregateTrade]


class CloseOrderParams(NamedTuple):
    """Parameters for creating a close position order."""

    symbol: str
    order_type_str: str
    side: str
    stop_price: float
    price_precision: int


class EntryOrderParams(NamedTuple):
    """Parameters for creating an entry order."""

    symbol: str
    order_type_str: str
    side: str
    quantity: float
    stop_price: float
    price_precision: int
    quantity_precision: int


class SymbolConfig(NamedTuple):
    """Configuration parameters for a specific trading symbol."""

    leverage: int
    maximum_quantity: float
    minimum_notional: float
    price_precision: int
    quantity_precision: int


class LaterCloseContext(NamedTuple):
    """Context for processing a later close order."""

    symbol: str
    decision: Decision
    current_direction: PositionDirection
    price_precision: int
    is_up_close: bool


class OrderPlacer:
    """Places orders on Binance futures exchange."""

    # Configuration for later entry orders: (order_type_str, side)
    LATER_ENTRY_ORDERS: ClassVar[dict[OrderType, tuple[str, str]]] = {
        OrderType.LATER_UP_BUY: ("STOP_MARKET", "BUY"),
        OrderType.LATER_DOWN_BUY: ("TAKE_PROFIT_MARKET", "BUY"),
        OrderType.LATER_UP_SELL: ("TAKE_PROFIT_MARKET", "SELL"),
        OrderType.LATER_DOWN_SELL: ("STOP_MARKET", "SELL"),
    }

    # Configuration for later close orders: is_up_close flag
    LATER_CLOSE_ORDERS: ClassVar[dict[OrderType, bool]] = {
        OrderType.LATER_UP_CLOSE: True,
        OrderType.LATER_DOWN_CLOSE: False,
    }

    def __init__(
        self,
        window: Window,
        api_requester: ApiRequester,
        config: OrderPlacerConfig,
        exchange_config: ExchangeConfig,
    ) -> None:
        """Initialize order placer."""
        self._window = window
        self._api_requester = api_requester
        self._account_state = config.account_state
        self._auto_order_record = config.auto_order_record
        self._aggregate_trades_queue = config.aggregate_trades_queue
        self._exchange_config = exchange_config

    async def place(self, decisions: dict[str, dict[OrderType, Decision]]) -> None:
        """Place orders based on decisions."""
        target_symbols = self._window.data_settings.target_symbols
        current_prices = await self._get_current_prices(target_symbols)

        # Cancel orders
        cancel_orders = self._prepare_cancel_orders(target_symbols, decisions)
        if cancel_orders:
            await gather(*(self._cancel_order(o) for o in cancel_orders))

        # Place now orders (market orders)
        now_orders = self._prepare_now_orders(target_symbols, decisions, current_prices)
        if now_orders:
            await gather(*(self._new_order(o) for o in now_orders))

        # Place book orders (limit orders)
        book_orders = self._prepare_book_orders(target_symbols, decisions)
        if book_orders:
            await gather(*(self._new_order(o) for o in book_orders))

        # Place later orders (stop/take-profit orders)
        later_orders = self._prepare_later_orders(target_symbols, decisions)
        if later_orders:
            await gather(*(self._new_order(o) for o in later_orders))

    async def _get_current_prices(self, target_symbols: list[str]) -> dict[str, float]:
        """Get current prices from recent aggregate trades."""
        current_timestamp = to_moment(datetime.now(UTC)).timestamp() * 1000
        current_prices: dict[str, float] = {}
        recent_trades = slice_deque(self._aggregate_trades_queue, 2 ** (10 + 6))

        for symbol in target_symbols:
            for trade in reversed(recent_trades):
                if trade.symbol != symbol:
                    continue
                if trade.timestamp < current_timestamp - 60 * 1000:
                    msg = "Recent price is not available for placing orders"
                    raise ValueError(msg)
                current_prices[symbol] = trade.price
                break

        return current_prices

    async def _cancel_order(self, payload: dict[str, Any]) -> None:
        """Cancel all open orders for a symbol."""
        await self._api_requester.binance(
            http_method="DELETE",
            path="/fapi/v1/allOpenOrders",
            payload=payload,
        )

    async def _new_order(self, payload: dict[str, Any]) -> None:
        """Place a new order and record it."""
        response = await self._api_requester.binance(
            http_method="POST",
            path="/fapi/v1/order",
            payload=payload,
        )
        order_symbol = response["symbol"]
        order_id = response["orderId"]
        timestamp = response["updateTime"] / 1000
        update_time = datetime.fromtimestamp(timestamp, tz=UTC)

        async with self._auto_order_record.write_lock as cell:
            while update_time in cell.data.index:
                update_time += timedelta(milliseconds=1)
            cell.data.loc[update_time, "SYMBOL"] = order_symbol
            cell.data.loc[update_time, "ORDER_ID"] = order_id
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await spawn_blocking(sort_data_frame, cell.data)

    def _prepare_cancel_orders(
        self,
        target_symbols: list[str],
        decisions: dict[str, dict[OrderType, Decision]],
    ) -> list[dict[str, Any]]:
        """Prepare cancel order payloads."""
        cancel_orders: list[dict[str, Any]] = []

        for symbol in target_symbols:
            if symbol not in decisions:
                continue
            if OrderType.CANCEL_ALL in decisions[symbol]:
                cancel_orders.append(
                    {
                        "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                        "symbol": symbol,
                    },
                )

        return cancel_orders

    def _prepare_now_orders(
        self,
        target_symbols: list[str],
        decisions: dict[str, dict[OrderType, Decision]],
        current_prices: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Prepare market orders."""
        now_orders: list[dict[str, Any]] = []

        for symbol in target_symbols:
            if symbol not in decisions:
                continue

            current_price = current_prices[symbol]
            leverage = self._exchange_config.leverages[symbol]
            maximum_quantity = self._exchange_config.maximum_quantities[symbol]
            minimum_notional = self._exchange_config.minimum_notionals[symbol]
            quantity_precision = self._exchange_config.quantity_precisions[symbol]
            current_direction = self._account_state.positions[symbol].direction

            # NOW_CLOSE
            if OrderType.NOW_CLOSE in decisions[symbol]:
                if current_direction != PositionDirection.NONE:
                    order_side = (
                        "SELL" if current_direction == PositionDirection.LONG else "BUY"
                    )
                    now_orders.append(
                        {
                            "timestamp": int(
                                datetime.now(UTC).timestamp() * 1000,
                            ),
                            "symbol": symbol,
                            "type": "MARKET",
                            "side": order_side,
                            "quantity": maximum_quantity,
                            "reduceOnly": True,
                            "newOrderRespType": "RESULT",
                        },
                    )
                else:
                    logger.warning("Cannot close position when there isn't any")

            # NOW_BUY
            if OrderType.NOW_BUY in decisions[symbol]:
                decision = decisions[symbol][OrderType.NOW_BUY]
                notional = max(minimum_notional, decision.margin * leverage)
                quantity = min(maximum_quantity, notional / current_price)
                now_orders.append(
                    {
                        "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                        "symbol": symbol,
                        "type": "MARKET",
                        "side": "BUY",
                        "quantity": ball_ceil(quantity, quantity_precision),
                        "newOrderRespType": "RESULT",
                    },
                )

            # NOW_SELL
            if OrderType.NOW_SELL in decisions[symbol]:
                decision = decisions[symbol][OrderType.NOW_SELL]
                notional = max(minimum_notional, decision.margin * leverage)
                quantity = min(maximum_quantity, notional / current_price)
                now_orders.append(
                    {
                        "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                        "symbol": symbol,
                        "type": "MARKET",
                        "side": "SELL",
                        "quantity": ball_ceil(quantity, quantity_precision),
                        "newOrderRespType": "RESULT",
                    },
                )

        return now_orders

    def _prepare_book_orders(
        self,
        target_symbols: list[str],
        decisions: dict[str, dict[OrderType, Decision]],
    ) -> list[dict[str, Any]]:
        """Prepare limit orders."""
        exchange_config = self._exchange_config
        book_orders: list[dict[str, Any]] = []

        for symbol in target_symbols:
            if symbol not in decisions:
                continue

            leverage = exchange_config.leverages[symbol]
            maximum_quantity = exchange_config.maximum_quantities[symbol]
            minimum_notional = exchange_config.minimum_notionals[symbol]
            price_precision = exchange_config.price_precisions[symbol]
            quantity_precision = exchange_config.quantity_precisions[symbol]

            # BOOK_BUY
            if OrderType.BOOK_BUY in decisions[symbol]:
                decision = decisions[symbol][OrderType.BOOK_BUY]
                notional = max(minimum_notional, decision.margin * leverage)
                boundary = decision.boundary
                quantity = min(maximum_quantity, notional / boundary)
                book_orders.append(
                    {
                        "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                        "symbol": symbol,
                        "type": "LIMIT",
                        "side": "BUY",
                        "quantity": ball_ceil(quantity, quantity_precision),
                        "price": round(boundary, price_precision),
                        "timeInForce": "GTC",
                    },
                )

            # BOOK_SELL
            if OrderType.BOOK_SELL in decisions[symbol]:
                decision = decisions[symbol][OrderType.BOOK_SELL]
                notional = max(minimum_notional, decision.margin * leverage)
                boundary = decision.boundary
                quantity = min(maximum_quantity, notional / boundary)
                book_orders.append(
                    {
                        "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                        "symbol": symbol,
                        "type": "LIMIT",
                        "side": "SELL",
                        "quantity": ball_ceil(quantity, quantity_precision),
                        "price": round(boundary, price_precision),
                        "timeInForce": "GTC",
                    },
                )

        return book_orders

    def _add_close_order(
        self,
        orders: list[dict[str, Any]],
        params: CloseOrderParams,
    ) -> None:
        """Add a close position order to the orders list."""
        orders.append(
            {
                "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "symbol": params.symbol,
                "type": params.order_type_str,
                "side": params.side,
                "stopPrice": round(params.stop_price, params.price_precision),
                "closePosition": True,
            },
        )

    def _add_entry_order(
        self,
        orders: list[dict[str, Any]],
        params: EntryOrderParams,
    ) -> None:
        """Add an entry order to the orders list."""
        orders.append(
            {
                "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "symbol": params.symbol,
                "type": params.order_type_str,
                "side": params.side,
                "quantity": ball_ceil(params.quantity, params.quantity_precision),
                "stopPrice": round(params.stop_price, params.price_precision),
            },
        )

    def _get_assumed_direction(
        self,
        symbol: str,
        decisions: dict[str, dict[OrderType, Decision]],
    ) -> PositionDirection:
        """Get the assumed position direction after now orders."""
        current_direction = self._account_state.positions[symbol].direction

        # Assume position from now orders
        if current_direction == PositionDirection.NONE:
            if OrderType.NOW_BUY in decisions.get(symbol, {}):
                return PositionDirection.LONG
            if OrderType.NOW_SELL in decisions.get(symbol, {}):
                return PositionDirection.SHORT

        # Assume position closed from now_close
        if (
            current_direction != PositionDirection.NONE
            and OrderType.NOW_CLOSE in decisions.get(symbol, {})
        ):
            return PositionDirection.NONE

        return current_direction

    def _handle_later_close_order(
        self,
        later_orders: list[dict[str, Any]],
        context: LaterCloseContext,
    ) -> None:
        """Handle LATER_UP_CLOSE or LATER_DOWN_CLOSE order."""
        if context.current_direction == PositionDirection.NONE:
            order_name = "later_up_close" if context.is_up_close else "later_down_close"
            logger.warning(
                "Cannot place `%s` with no open position",
                order_name,
            )
            return

        is_long = context.current_direction == PositionDirection.LONG
        if context.is_up_close:
            order_type_str = "TAKE_PROFIT_MARKET" if is_long else "STOP_MARKET"
        else:
            order_type_str = "STOP_MARKET" if is_long else "TAKE_PROFIT_MARKET"

        self._add_close_order(
            later_orders,
            CloseOrderParams(
                symbol=context.symbol,
                order_type_str=order_type_str,
                side="SELL" if is_long else "BUY",
                stop_price=context.decision.boundary,
                price_precision=context.price_precision,
            ),
        )

    def _create_later_entry_order(
        self,
        symbol: str,
        decision: Decision,
        config: SymbolConfig,
        order_type_str: str,
        side: str,
    ) -> EntryOrderParams:
        """Create parameters for LATER_UP/DOWN_BUY and LATER_UP/DOWN_SELL orders."""
        notional = max(config.minimum_notional, decision.margin * config.leverage)
        quantity = min(config.maximum_quantity, notional / decision.boundary)
        return EntryOrderParams(
            symbol=symbol,
            order_type_str=order_type_str,
            side=side,
            quantity=quantity,
            stop_price=decision.boundary,
            price_precision=config.price_precision,
            quantity_precision=config.quantity_precision,
        )

    def _prepare_later_orders(
        self,
        target_symbols: list[str],
        decisions: dict[str, dict[OrderType, Decision]],
    ) -> list[dict[str, Any]]:
        """Prepare stop/take-profit orders."""
        later_orders: list[dict[str, Any]] = []

        for symbol in target_symbols:
            if symbol not in decisions:
                continue

            config = SymbolConfig(
                leverage=self._exchange_config.leverages[symbol],
                maximum_quantity=self._exchange_config.maximum_quantities[symbol],
                minimum_notional=self._exchange_config.minimum_notionals[symbol],
                price_precision=self._exchange_config.price_precisions[symbol],
                quantity_precision=self._exchange_config.quantity_precisions[symbol],
            )
            current_direction = self._get_assumed_direction(symbol, decisions)

            # Handle later close orders
            for order_type, is_up_close in self.LATER_CLOSE_ORDERS.items():
                if order_type in decisions[symbol]:
                    context = LaterCloseContext(
                        symbol=symbol,
                        decision=decisions[symbol][order_type],
                        current_direction=current_direction,
                        price_precision=config.price_precision,
                        is_up_close=is_up_close,
                    )
                    self._handle_later_close_order(later_orders, context)

            # Handle later entry orders
            for order_type, (order_type_str, side) in self.LATER_ENTRY_ORDERS.items():
                if order_type in decisions[symbol]:
                    params = self._create_later_entry_order(
                        symbol,
                        decisions[symbol][order_type],
                        config,
                        order_type_str,
                        side,
                    )
                    self._add_entry_order(later_orders, params)

        return later_orders
