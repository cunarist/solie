from datetime import datetime, timedelta, timezone

import pandas as pd


def do(
    symbol: str,
    recent_candle_data: pd.DataFrame,
    aggtrades: pd.DataFrame,
    moment_to_fill_from: datetime,
    last_fetched_time: datetime,
) -> pd.DataFrame:
    fill_moment = moment_to_fill_from

    while fill_moment < last_fetched_time - timedelta(seconds=10):
        block_start = fill_moment
        block_end = fill_moment + timedelta(seconds=10)

        aggtrade_prices = []
        aggtrade_volumes = []
        for _, aggtrade in sorted(aggtrades.items()):
            # sorted by time
            aggtrade_time = datetime.fromtimestamp(
                aggtrade["T"] / 1000, tz=timezone.utc
            )
            if block_start <= aggtrade_time < block_end:
                aggtrade_prices.append(float(aggtrade["p"]))
                aggtrade_volumes.append(float(aggtrade["q"]))

        can_write = True

        if len(aggtrade_prices) == 0:
            # when there are no trades
            inspect_sr = recent_candle_data[(symbol, "Close")]
            inspect_sr = inspect_sr.sort_index()
            last_prices = inspect_sr[:fill_moment].dropna()
            if len(last_prices) == 0:
                # when there are no previous data
                # because new data folder was created
                can_write = False
                last_price = 0
            else:
                last_price = last_prices.iloc[-1]
            open_price = last_price
            high_price = last_price
            low_price = last_price
            close_price = last_price
            sum_volume = 0
        else:
            open_price = aggtrade_prices[0]
            high_price = max(aggtrade_prices)
            low_price = min(aggtrade_prices)
            close_price = aggtrade_prices[-1]
            sum_volume = sum(aggtrade_volumes)

        if can_write:
            column = (symbol, "Open")
            recent_candle_data.loc[fill_moment, column] = open_price
            column = (symbol, "High")
            recent_candle_data.loc[fill_moment, column] = high_price
            column = (symbol, "Low")
            recent_candle_data.loc[fill_moment, column] = low_price
            column = (symbol, "Close")
            recent_candle_data.loc[fill_moment, column] = close_price
            column = (symbol, "Volume")
            recent_candle_data.loc[fill_moment, column] = sum_volume

        fill_moment += timedelta(seconds=10)

    recent_candle_data = recent_candle_data.sort_index(axis="index")
    recent_candle_data = recent_candle_data.sort_index(axis="columns")

    return recent_candle_data
