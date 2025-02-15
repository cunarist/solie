from typing import Any

import pandas as pd
import pandas_ta as ta
from solie import (
    AccountState,
    Decision,
    FixedStrategy,
    OrderType,
    PositionDirection,
)


class MyStrategy(FixedStrategy):
    def create_indicators(
        self,
        target_symbols: list[str],
        candle_data: pd.DataFrame,
        new_indicators: dict[str, pd.Series],
    ):
        short_period = 180
        long_period = 720

        for symbol in target_symbols:
            # Get candle data
            close_sr = candle_data[f"{symbol}/CLOSE"]
            volume_sr = candle_data[f"{symbol}/VOLUME"]

            # Price scale indicators
            price_sma_one: pd.Series = ta.sma(close_sr, short_period)  # type:ignore
            price_sma_two: pd.Series = ta.sma(close_sr, long_period)  # type:ignore
            new_indicators[f"{symbol}/PRICE/SMA_ONE(#00BBFF)"] = price_sma_one
            new_indicators[f"{symbol}/PRICE/SMA_TWO(#FF6666)"] = price_sma_two

            # Volume scale indicators
            volume_sma_one: pd.Series = ta.sma(volume_sr, short_period * 2)  # type:ignore
            volume_sma_two: pd.Series = ta.sma(volume_sr, long_period * 2)  # type:ignore
            new_indicators[f"{symbol}/VOLUME/SMA_ONE"] = volume_sma_one
            new_indicators[f"{symbol}/VOLUME/SMA_TWO"] = volume_sma_two

            # Abstract scale indicators
            wildness = volume_sma_one / volume_sma_two
            wildness[wildness > 1.5] = 1.5
            new_indicators[f"{symbol}/ABSTRACT/WILDNESS"] = wildness

    def create_decisions(
        self,
        target_symbols: list[str],
        account_state: AccountState,
        current_candle_data: dict[str, float],
        current_indicators: dict[str, float],
        scribbles: dict[Any, Any],
        new_decisions: dict[str, dict[OrderType, Decision]],
    ):
        acquire_ratio = 0.8 / len(target_symbols)  # Split asset by symbol count
        wallet_balance = account_state.wallet_balance

        for symbol in target_symbols:
            _current_price = current_candle_data[f"{symbol}/CLOSE"]
            price_sma_one = current_indicators[f"{symbol}/PRICE/SMA_ONE(#00BBFF)"]
            price_sma_two = current_indicators[f"{symbol}/PRICE/SMA_TWO(#FF6666)"]

            position = account_state.positions[symbol]

            scribbles["MY_KEY"] = True  # Remember something
            _my_value = scribbles.get("MY_KEY", False)  # Get it later

            if position.direction == PositionDirection.NONE:
                if price_sma_one > price_sma_two:
                    new_decisions[symbol][OrderType.NOW_BUY] = Decision(
                        margin=acquire_ratio * wallet_balance
                    )
                elif price_sma_one < price_sma_two:
                    new_decisions[symbol][OrderType.NOW_SELL] = Decision(
                        margin=acquire_ratio * wallet_balance
                    )

            elif position.direction == PositionDirection.LONG:
                if price_sma_one < price_sma_two:
                    # Flip
                    new_decisions[symbol][OrderType.NOW_SELL] = Decision(
                        margin=position.margin + acquire_ratio * wallet_balance
                    )

            elif position.direction == PositionDirection.SHORT:
                if price_sma_one > price_sma_two:
                    # Flip
                    new_decisions[symbol][OrderType.NOW_BUY] = Decision(
                        margin=position.margin + acquire_ratio * wallet_balance
                    )


__all__ = ["MyStrategy"]
