from typing import Any

import pandas as pd
import pandas_ta as ta

from solie import (
    AccountState,
    Decision,
    DecisionInput,
    IndicatorInput,
    OrderType,
    Position,
    PositionDirection,
    RiskLevel,
)


class SilentStrategy:
    code_name = "SILENT"
    readable_name = "Silent Strategy"
    version = "0.1"
    description = "A silent strategy that does nothing"
    risk_level = RiskLevel.LOW
    parallel_simulation_chunk_days: int | None = 30

    def create_indicators(self, given: IndicatorInput):
        pass

    def create_decisions(self, given: DecisionInput):
        pass


class ExampleStrategy:
    code_name = "EXAMPL"
    readable_name = "Fixed Strategy"
    version = "1.2"
    description = "A fixed strategy for demonstration"
    risk_level = RiskLevel.HIGH
    parallel_simulation_chunk_days: int | None = 30

    def create_indicators(self, given: IndicatorInput):
        target_symbols: list[str] = given.target_symbols
        candle_data: pd.DataFrame = given.candle_data
        new_indicators: dict[str, pd.Series] = given.new_indicators

        short_period = 90
        long_period = 360

        for symbol in target_symbols:
            # Get candle data
            close_sr: pd.Series = candle_data[f"{symbol}/CLOSE"]
            volume_sr: pd.Series = candle_data[f"{symbol}/VOLUME"]

            # Price scale indicators
            price_sma_one: pd.Series = ta.sma(close_sr, short_period)
            price_sma_two: pd.Series = ta.sma(close_sr, long_period)
            new_indicators[f"{symbol}/PRICE/SMA_ONE(#00FFA6)"] = price_sma_one
            new_indicators[f"{symbol}/PRICE/SMA_TWO(#C261FF)"] = price_sma_two

            # Volume scale indicators
            volume_sma_one: pd.Series = ta.sma(volume_sr, short_period * 2)
            volume_sma_two: pd.Series = ta.sma(volume_sr, long_period * 2)
            new_indicators[f"{symbol}/VOLUME/SMA_ONE"] = volume_sma_one
            new_indicators[f"{symbol}/VOLUME/SMA_TWO"] = volume_sma_two

            # Abstract scale indicators
            wildness = volume_sma_one / volume_sma_two
            wildness[wildness > 1.5] = 1.5
            new_indicators[f"{symbol}/ABSTRACT/WILDNESS"] = wildness

    def create_decisions(self, given: DecisionInput):
        target_symbols: list[str] = given.target_symbols
        account_state: AccountState = given.account_state
        current_candle_data: dict[str, float] = given.current_candle_data
        current_indicators: dict[str, float] = given.current_indicators
        scribbles: dict[Any, Any] = given.scribbles
        new_decisions: dict[str, dict[OrderType, Decision]] = given.new_decisions

        acquire_ratio = 0.8 / len(target_symbols)  # Split asset by symbol count
        wallet_balance = account_state.wallet_balance

        for symbol in target_symbols:
            _current_price = current_candle_data[f"{symbol}/CLOSE"]
            price_sma_one = current_indicators[f"{symbol}/PRICE/SMA_ONE(#00FFA6)"]
            price_sma_two = current_indicators[f"{symbol}/PRICE/SMA_TWO(#C261FF)"]

            position: Position = account_state.positions[symbol]

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
