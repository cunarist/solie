"""Binance exchange watcher for account synchronization."""

import math
from asyncio import gather
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Any, NamedTuple

import pandas as pd

from solie.common import spawn_blocking
from solie.logic import AccountListener, ParseOrderTypeParams
from solie.utility import (
    AccountState,
    ApiRequester,
    ApiRequestError,
    Decision,
    OpenOrder,
    OrderType,
    PositionDirection,
    RWLock,
    ServerType,
    TransactionSettings,
    internet_connected,
    list_to_dict,
    sort_data_frame,
    sort_series,
    to_moment,
)
from solie.window import Window

logger = getLogger(__name__)


class ExchangeConfig(NamedTuple):
    """Exchange configuration data."""

    maximum_quantities: dict[str, float]
    minimum_notionals: dict[str, float]
    price_precisions: dict[str, int]
    quantity_precisions: dict[str, int]
    maximum_leverages: dict[str, int]
    leverages: dict[str, int]


class StateConfig(NamedTuple):
    """State and configuration for BinanceWatcher."""

    account_state: AccountState
    transaction_settings: TransactionSettings
    unrealized_changes: RWLock[pd.Series]
    asset_record: RWLock[pd.DataFrame]


class BinanceWatcher:
    """Watches Binance exchange and synchronizes account state."""

    def __init__(
        self,
        window: Window,
        api_requester: ApiRequester,
        state_config: StateConfig,
        exchange_config: ExchangeConfig,
    ) -> None:
        """Initialize Binance watcher."""
        self._window = window
        self._api_requester = api_requester
        self._account_state = state_config.account_state
        self._transaction_settings = state_config.transaction_settings
        self._unrealized_changes = state_config.unrealized_changes
        self._asset_record = state_config.asset_record
        self._exchange_config = exchange_config

        self.is_key_restrictions_satisfied = True

    async def watch(
        self,
        place_orders_callback: Callable[[dict[str, dict[OrderType, Decision]]], Any],
    ) -> None:
        """Watch Binance and update all account state."""
        target_symbols = self._window.data_settings.target_symbols
        asset_token = self._window.data_settings.asset_token

        if not internet_connected():
            return

        current_moment = to_moment(datetime.now(UTC))
        before_moment = current_moment - timedelta(seconds=10)

        # Fetch exchange information
        about_exchange = await self._fetch_exchange_info()
        self._process_exchange_info(about_exchange)

        # Fetch leverage brackets
        try:
            about_brackets = await self._fetch_leverage_brackets()
            self._process_leverage_brackets(about_brackets)
        except ApiRequestError:
            return

        # Fetch account information
        try:
            about_account = await self._fetch_account_info()
        except ApiRequestError:
            return

        # Fetch open orders
        about_open_orders = await self._fetch_open_orders(target_symbols)

        # Update account state
        self._update_account_state(
            target_symbols,
            asset_token,
            current_moment,
            about_account,
            about_open_orders,
        )

        # Record unrealized change
        await self._record_unrealized_change(asset_token, about_account, before_moment)

        # Initialize asset record if needed
        await self._initialize_asset_record(asset_token, about_account)

        # Handle wallet balance changes
        await self._handle_wallet_balance_changes(asset_token, about_account)

        # Correct account mode if automation is on
        if self._transaction_settings.should_transact:
            await self._correct_account_mode(
                target_symbols,
                about_account,
                place_orders_callback,
            )

        # Check API restrictions
        await self._check_api_restrictions()

    async def _fetch_exchange_info(self) -> dict[str, Any]:
        """Fetch exchange information."""
        payload: dict[str, Any] = {}
        return await self._api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload=payload,
        )

    def _process_exchange_info(self, about_exchange: dict[str, Any]) -> None:
        """Process exchange information."""
        for about_symbol in about_exchange["symbols"]:
            symbol = about_symbol["symbol"]
            about_filters = about_symbol["filters"]
            about_filters_keyed = list_to_dict(about_filters, "filterType")

            self._exchange_config.minimum_notionals[symbol] = float(
                about_filters_keyed["MIN_NOTIONAL"]["notional"],
            )
            self._exchange_config.maximum_quantities[symbol] = min(
                float(about_filters_keyed["LOT_SIZE"]["maxQty"]),
                float(about_filters_keyed["MARKET_LOT_SIZE"]["maxQty"]),
            )

            ticksize = float(about_filters_keyed["PRICE_FILTER"]["tickSize"])
            self._exchange_config.price_precisions[symbol] = int(
                math.log10(1 / ticksize),
            )

            stepsize = float(about_filters_keyed["LOT_SIZE"]["stepSize"])
            self._exchange_config.quantity_precisions[symbol] = int(
                math.log10(1 / stepsize),
            )

    async def _fetch_leverage_brackets(self) -> list[dict[str, Any]]:
        """Fetch leverage bracket information."""
        payload = {
            "timestamp": int(datetime.now(UTC).timestamp() * 1000),
        }
        return await self._api_requester.binance(
            http_method="GET",
            path="/fapi/v1/leverageBracket",
            payload=payload,
        )

    def _process_leverage_brackets(self, about_brackets: list[dict[str, Any]]) -> None:
        """Process leverage brackets."""
        for about_bracket in about_brackets:
            symbol = about_bracket["symbol"]
            max_leverage = about_bracket["brackets"][0]["initialLeverage"]
            self._exchange_config.maximum_leverages[symbol] = max_leverage

    async def _fetch_account_info(self) -> dict[str, Any]:
        """Fetch account information."""
        payload = {
            "timestamp": int(datetime.now(UTC).timestamp() * 1000),
        }
        return await self._api_requester.binance(
            http_method="GET",
            path="/fapi/v2/account",
            payload=payload,
        )

    async def _fetch_open_orders(
        self,
        target_symbols: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch open orders for all symbols."""
        about_open_orders: dict[str, list[dict[str, Any]]] = {}

        async def job(symbol: str) -> None:
            payload = {
                "symbol": symbol,
                "timestamp": int(datetime.now(UTC).timestamp() * 1000),
            }
            about_open_orders[symbol] = await self._api_requester.binance(
                http_method="GET",
                path="/fapi/v1/openOrders",
                payload=payload,
            )

        await gather(*(job(s) for s in target_symbols))
        return about_open_orders

    def _update_account_state(
        self,
        target_symbols: list[str],
        asset_token: str,
        current_moment: datetime,
        about_account: dict[str, Any],
        about_open_orders: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Update account state."""
        self._account_state.observed_until = current_moment

        # Update wallet balance
        about_assets = about_account["assets"]
        about_assets_keyed = list_to_dict(about_assets, "asset")
        about_asset = about_assets_keyed[asset_token]
        self._account_state.wallet_balance = float(about_asset["walletBalance"])

        about_positions = about_account["positions"]
        about_positions_keyed = list_to_dict(about_positions, "symbol")

        # Update positions
        for symbol in target_symbols:
            about_position = about_positions_keyed[symbol]

            notional = float(about_position["notional"])
            if notional > 0.0:
                direction = PositionDirection.LONG
            elif notional < 0.0:
                direction = PositionDirection.SHORT
            else:
                direction = PositionDirection.NONE

            entry_price = float(about_position["entryPrice"])
            update_time = int(float(about_position["updateTime"]) / 1000)
            update_time = datetime.fromtimestamp(update_time, tz=UTC)
            leverage = int(about_position["leverage"])
            amount = float(about_position["positionAmt"])
            margin = abs(amount) * entry_price / leverage

            position = self._account_state.positions[symbol]
            position.margin = margin
            position.direction = direction
            position.entry_price = entry_price
            position.update_time = update_time

            self._exchange_config.leverages[symbol] = leverage

        # Update open orders
        self._update_open_orders(
            target_symbols,
            about_positions_keyed,
            about_open_orders,
        )

    def _update_open_orders(
        self,
        target_symbols: list[str],
        about_positions_keyed: dict[str, Any],
        about_open_orders: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Update open orders from API response."""
        open_orders: dict[str, dict[int, OpenOrder]] = {s: {} for s in target_symbols}

        # Create temporary listener for parsing
        listener = AccountListener(
            window=self._window,
            account_state=self._account_state,
            leverages=self._exchange_config.leverages,
            asset_record=self._asset_record,
            auto_order_record=RWLock(pd.DataFrame()),
        )

        for symbol in target_symbols:
            leverage = int(about_positions_keyed[symbol]["leverage"])

            for about_open_order in about_open_orders[symbol]:
                params = ParseOrderTypeParams(
                    order_type=str(about_open_order["type"]),
                    side=str(about_open_order["side"]),
                    close_position=bool(about_open_order["closePosition"]),
                    price=float(about_open_order["price"]),
                    stop_price=float(about_open_order["stopPrice"]),
                    origianal_quantity=float(about_open_order["origQty"]),
                    executed_quantity=float(about_open_order["executedQty"]),
                    leverage=leverage,
                )
                parsed = listener.parse_order_type(params)

                if parsed:
                    open_orders[symbol][about_open_order["orderId"]] = OpenOrder(
                        order_type=parsed.order_type,
                        boundary=parsed.boundary,
                        left_margin=parsed.left_margin,
                    )

        self._account_state.open_orders = open_orders

    async def _record_unrealized_change(
        self,
        asset_token: str,
        about_account: dict[str, Any],
        before_moment: datetime,
    ) -> None:
        """Record unrealized profit change."""
        about_assets = about_account["assets"]
        about_assets_keyed = list_to_dict(about_assets, "asset")
        about_asset = about_assets_keyed[asset_token]

        wallet_balance = float(about_asset["walletBalance"])
        if wallet_balance != 0:
            unrealized_profit = float(about_asset["unrealizedProfit"])
            unrealized_change = unrealized_profit / wallet_balance
        else:
            unrealized_change = 0

        async with self._unrealized_changes.write_lock as cell:
            cell.data[before_moment] = unrealized_change
            if not cell.data.index.is_monotonic_increasing:
                cell.data = await spawn_blocking(sort_series, cell.data)

    async def _initialize_asset_record(
        self,
        asset_token: str,
        about_account: dict[str, Any],
    ) -> None:
        """Initialize asset record if blank."""
        async with self._asset_record.write_lock as cell:
            if len(cell.data) == 0:
                about_assets = about_account["assets"]
                about_assets_keyed = list_to_dict(about_assets, "asset")
                about_asset = about_assets_keyed[asset_token]
                wallet_balance = float(about_asset["walletBalance"])
                current_time = datetime.now(UTC)
                cell.data.loc[current_time, "CAUSE"] = "OTHER"
                cell.data.loc[current_time, "RESULT_ASSET"] = wallet_balance

    async def _handle_wallet_balance_changes(
        self,
        asset_token: str,
        about_account: dict[str, Any],
    ) -> None:
        """Handle wallet balance changes."""
        about_assets = about_account["assets"]
        about_assets_keyed = list_to_dict(about_assets, "asset")
        about_asset = about_assets_keyed[asset_token]
        wallet_balance = float(about_asset["walletBalance"])

        async with self._asset_record.read_lock as cell:
            if len(cell.data) == 0:
                return
            df_index: pd.DatetimeIndex = cell.data.index  # type:ignore
            last_index = df_index[-1]
            last_asset = float(cell.data.loc[last_index, "RESULT_ASSET"])  # type:ignore

        if wallet_balance == 0:
            pass
        elif abs(wallet_balance - last_asset) / wallet_balance > 10**-9:
            async with self._asset_record.write_lock as cell:
                current_time = datetime.now(UTC)
                cell.data.loc[current_time, "CAUSE"] = "OTHER"
                cell.data.loc[current_time, "RESULT_ASSET"] = wallet_balance
                if not cell.data.index.is_monotonic_increasing:
                    cell.data = await spawn_blocking(sort_data_frame, cell.data)
        else:
            async with self._asset_record.write_lock as cell:
                df_index: pd.DatetimeIndex = cell.data.index  # type:ignore
                last_index = df_index[-1]
                cell.data.loc[last_index, "RESULT_ASSET"] = wallet_balance

    async def _correct_account_mode(
        self,
        target_symbols: list[str],
        about_account: dict[str, Any],
        place_orders_callback: Callable[[dict[str, dict[OrderType, Decision]]], Any],
    ) -> None:
        """Correct account mode when automation is on."""
        about_positions = about_account["positions"]
        about_positions_keyed = list_to_dict(about_positions, "symbol")

        await self._correct_leverage(target_symbols, about_positions_keyed)
        await self._correct_margin_type(
            target_symbols,
            about_positions_keyed,
            place_orders_callback,
        )
        await self._set_account_settings()

    async def _correct_leverage(
        self,
        target_symbols: list[str],
        about_positions_keyed: dict[str, Any],
    ) -> None:
        """Correct leverage for all symbols."""

        async def job(symbol: str) -> None:
            current_leverage = int(about_positions_keyed[symbol]["leverage"])
            desired_leverage = self._transaction_settings.desired_leverage
            max_leverage = self._exchange_config.maximum_leverages.get(symbol, 125)
            goal_leverage = min(desired_leverage, max_leverage)

            if current_leverage != goal_leverage:
                payload = {
                    "symbol": symbol,
                    "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                    "leverage": goal_leverage,
                }
                await self._api_requester.binance(
                    http_method="POST",
                    path="/fapi/v1/leverage",
                    payload=payload,
                )

        await gather(*(job(s) for s in target_symbols))

    async def _correct_margin_type(
        self,
        target_symbols: list[str],
        about_positions_keyed: dict[str, Any],
        place_orders_callback: Callable[[dict[str, dict[OrderType, Decision]]], Any],
    ) -> None:
        """Correct margin type for all symbols."""

        async def job(symbol: str) -> None:
            about_position = about_positions_keyed[symbol]
            if about_position["isolated"]:
                # Close position if exists
                if float(about_position["notional"]) != 0:
                    decisions = {symbol: {OrderType.NOW_CLOSE: Decision()}}
                    await place_orders_callback(decisions)

                # Change to crossed margin
                payload = {
                    "symbol": symbol,
                    "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                    "marginType": "CROSSED",
                }
                await self._api_requester.binance(
                    http_method="POST",
                    path="/fapi/v1/marginType",
                    payload=payload,
                )

        await gather(*(job(s) for s in target_symbols))

    async def _set_account_settings(self) -> None:
        """Set multi-asset margin and position side mode."""
        try:
            payload = {
                "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "multiAssetsMargin": "false",
            }
            await self._api_requester.binance(
                http_method="POST",
                path="/fapi/v1/multiAssetsMargin",
                payload=payload,
            )
        except ApiRequestError:
            pass

        try:
            payload = {
                "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "dualSidePosition": "false",
            }
            await self._api_requester.binance(
                http_method="POST",
                path="/fapi/v1/positionSide/dual",
                payload=payload,
            )
        except ApiRequestError:
            pass

    async def _check_api_restrictions(self) -> None:
        """Check API key restrictions."""
        payload = {
            "timestamp": int(datetime.now(UTC).timestamp() * 1000),
        }
        response = await self._api_requester.binance(
            http_method="GET",
            path="/sapi/v1/account/apiRestrictions",
            payload=payload,
            server_type=ServerType.SPOT,
        )

        self.is_key_restrictions_satisfied = response.get("enableFutures", False)
