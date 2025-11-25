"""Order placer for Binance futures trading."""

from asyncio import gather
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any, NamedTuple

import pandas as pd

from solie.common import spawn_blocking
from solie.utility import (
    AccountState,
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
    aggregate_trades_queue: Any


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


class OrderPlacer:
    """Places orders on Binance futures exchange."""

    def __init__(
        self,
        window: Window,
        api_requester: ApiRequester,
        config: OrderPlacerConfig,
        exchange_config: ExchangeConfig,
    ) -> None:
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
        current_timestamp = to_moment(datetime.now(timezone.utc)).timestamp() * 1000
        current_prices: dict[str, float] = {}
        recent_trades = slice_deque(self._aggregate_trades_queue, 2 ** (10 + 6))

        for symbol in target_symbols:
            for trade in reversed(recent_trades):
                if trade.symbol != symbol:
                    continue
                if trade.timestamp < current_timestamp - 60 * 1000:
                    raise ValueError("Recent price is not available for placing orders")
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
        update_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)

        async with self._auto_order_record.write_lock as cell:
            while update_time in cell.data.index:
                update_time += timedelta(milliseconds=1)
            cell.data.loc[update_time, "SYMBOL"] = order_symbol
            cell.data.loc[update_time, "ORDER_ID"] = order_id
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await spawn_blocking(sort_data_frame, cell.data)

    def _prepare_cancel_orders(
        self, target_symbols: list[str], decisions: dict[str, dict[OrderType, Decision]]
    ) -> list[dict[str, Any]]:
        """Prepare cancel order payloads."""
        cancel_orders: list[dict[str, Any]] = []

        for symbol in target_symbols:
            if symbol not in decisions:
                continue
            if OrderType.CANCEL_ALL in decisions[symbol]:
                cancel_orders.append(
                    {
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "symbol": symbol,
                    }
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
                                datetime.now(timezone.utc).timestamp() * 1000
                            ),
                            "symbol": symbol,
                            "type": "MARKET",
                            "side": order_side,
                            "quantity": maximum_quantity,
                            "reduceOnly": True,
                            "newOrderRespType": "RESULT",
                        }
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
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "symbol": symbol,
                        "type": "MARKET",
                        "side": "BUY",
                        "quantity": ball_ceil(quantity, quantity_precision),
                        "newOrderRespType": "RESULT",
                    }
                )

            # NOW_SELL
            if OrderType.NOW_SELL in decisions[symbol]:
                decision = decisions[symbol][OrderType.NOW_SELL]
                notional = max(minimum_notional, decision.margin * leverage)
                quantity = min(maximum_quantity, notional / current_price)
                now_orders.append(
                    {
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "symbol": symbol,
                        "type": "MARKET",
                        "side": "SELL",
                        "quantity": ball_ceil(quantity, quantity_precision),
                        "newOrderRespType": "RESULT",
                    }
                )

        return now_orders

    def _prepare_book_orders(
        self, target_symbols: list[str], decisions: dict[str, dict[OrderType, Decision]]
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
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "symbol": symbol,
                        "type": "LIMIT",
                        "side": "BUY",
                        "quantity": ball_ceil(quantity, quantity_precision),
                        "price": round(boundary, price_precision),
                        "timeInForce": "GTC",
                    }
                )

            # BOOK_SELL
            if OrderType.BOOK_SELL in decisions[symbol]:
                decision = decisions[symbol][OrderType.BOOK_SELL]
                notional = max(minimum_notional, decision.margin * leverage)
                boundary = decision.boundary
                quantity = min(maximum_quantity, notional / boundary)
                book_orders.append(
                    {
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "symbol": symbol,
                        "type": "LIMIT",
                        "side": "SELL",
                        "quantity": ball_ceil(quantity, quantity_precision),
                        "price": round(boundary, price_precision),
                        "timeInForce": "GTC",
                    }
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
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "symbol": params.symbol,
                "type": params.order_type_str,
                "side": params.side,
                "stopPrice": round(params.stop_price, params.price_precision),
                "closePosition": True,
            }
        )

    def _add_entry_order(
        self,
        orders: list[dict[str, Any]],
        params: EntryOrderParams,
    ) -> None:
        """Add an entry order to the orders list."""
        orders.append(
            {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "symbol": params.symbol,
                "type": params.order_type_str,
                "side": params.side,
                "quantity": ball_ceil(params.quantity, params.quantity_precision),
                "stopPrice": round(params.stop_price, params.price_precision),
            }
        )

    def _get_assumed_direction(
        self, symbol: str, decisions: dict[str, dict[OrderType, Decision]]
    ) -> PositionDirection:
        """Get the assumed position direction after now orders."""
        current_direction = self._account_state.positions[symbol].direction

        # Assume position from now orders
        if current_direction == PositionDirection.NONE:
            if OrderType.NOW_BUY in decisions.get(symbol, {}):
                return PositionDirection.LONG
            elif OrderType.NOW_SELL in decisions.get(symbol, {}):
                return PositionDirection.SHORT

        # Assume position closed from now_close
        if current_direction != PositionDirection.NONE:
            if OrderType.NOW_CLOSE in decisions.get(symbol, {}):
                return PositionDirection.NONE

        return current_direction

    def _prepare_later_orders(
        self, target_symbols: list[str], decisions: dict[str, dict[OrderType, Decision]]
    ) -> list[dict[str, Any]]:
        """Prepare stop/take-profit orders."""
        later_orders: list[dict[str, Any]] = []

        for symbol in target_symbols:
            if symbol not in decisions:
                continue

            leverage = self._exchange_config.leverages[symbol]
            maximum_quantity = self._exchange_config.maximum_quantities[symbol]
            minimum_notional = self._exchange_config.minimum_notionals[symbol]
            price_precision = self._exchange_config.price_precisions[symbol]
            quantity_precision = self._exchange_config.quantity_precisions[symbol]
            current_direction = self._get_assumed_direction(symbol, decisions)

            # LATER_UP_CLOSE
            if OrderType.LATER_UP_CLOSE in decisions[symbol]:
                decision = decisions[symbol][OrderType.LATER_UP_CLOSE]
                if current_direction != PositionDirection.NONE:
                    is_long = current_direction == PositionDirection.LONG
                    self._add_close_order(
                        later_orders,
                        CloseOrderParams(
                            symbol=symbol,
                            order_type_str="TAKE_PROFIT_MARKET"
                            if is_long
                            else "STOP_MARKET",
                            side="SELL" if is_long else "BUY",
                            stop_price=decision.boundary,
                            price_precision=price_precision,
                        ),
                    )
                else:
                    logger.warning(
                        "Cannot place `later_up_close` with no open position"
                    )

            # LATER_DOWN_CLOSE
            if OrderType.LATER_DOWN_CLOSE in decisions[symbol]:
                decision = decisions[symbol][OrderType.LATER_DOWN_CLOSE]
                if current_direction != PositionDirection.NONE:
                    is_long = current_direction == PositionDirection.LONG
                    self._add_close_order(
                        later_orders,
                        CloseOrderParams(
                            symbol=symbol,
                            order_type_str="STOP_MARKET"
                            if is_long
                            else "TAKE_PROFIT_MARKET",
                            side="SELL" if is_long else "BUY",
                            stop_price=decision.boundary,
                            price_precision=price_precision,
                        ),
                    )
                else:
                    logger.warning(
                        "Cannot place `later_down_close` with no open position"
                    )

            # LATER_UP_BUY
            if OrderType.LATER_UP_BUY in decisions[symbol]:
                decision = decisions[symbol][OrderType.LATER_UP_BUY]
                notional = max(minimum_notional, decision.margin * leverage)
                quantity = min(maximum_quantity, notional / decision.boundary)
                self._add_entry_order(
                    later_orders,
                    EntryOrderParams(
                        symbol=symbol,
                        order_type_str="STOP_MARKET",
                        side="BUY",
                        quantity=quantity,
                        stop_price=decision.boundary,
                        price_precision=price_precision,
                        quantity_precision=quantity_precision,
                    ),
                )

            # LATER_DOWN_BUY
            if OrderType.LATER_DOWN_BUY in decisions[symbol]:
                decision = decisions[symbol][OrderType.LATER_DOWN_BUY]
                notional = max(minimum_notional, decision.margin * leverage)
                quantity = min(maximum_quantity, notional / decision.boundary)
                self._add_entry_order(
                    later_orders,
                    EntryOrderParams(
                        symbol=symbol,
                        order_type_str="TAKE_PROFIT_MARKET",
                        side="BUY",
                        quantity=quantity,
                        stop_price=decision.boundary,
                        price_precision=price_precision,
                        quantity_precision=quantity_precision,
                    ),
                )

            # LATER_UP_SELL
            if OrderType.LATER_UP_SELL in decisions[symbol]:
                decision = decisions[symbol][OrderType.LATER_UP_SELL]
                notional = max(minimum_notional, decision.margin * leverage)
                quantity = min(maximum_quantity, notional / decision.boundary)
                self._add_entry_order(
                    later_orders,
                    EntryOrderParams(
                        symbol=symbol,
                        order_type_str="TAKE_PROFIT_MARKET",
                        side="SELL",
                        quantity=quantity,
                        stop_price=decision.boundary,
                        price_precision=price_precision,
                        quantity_precision=quantity_precision,
                    ),
                )

            # LATER_DOWN_SELL
            if OrderType.LATER_DOWN_SELL in decisions[symbol]:
                decision = decisions[symbol][OrderType.LATER_DOWN_SELL]
                notional = max(minimum_notional, decision.margin * leverage)
                quantity = min(maximum_quantity, notional / decision.boundary)
                self._add_entry_order(
                    later_orders,
                    EntryOrderParams(
                        symbol=symbol,
                        order_type_str="STOP_MARKET",
                        side="SELL",
                        quantity=quantity,
                        stop_price=decision.boundary,
                        price_precision=price_precision,
                        quantity_precision=quantity_precision,
                    ),
                )

        return later_orders
