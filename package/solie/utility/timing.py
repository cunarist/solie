from collections import deque
from datetime import datetime, timedelta

task_durations: dict[str, deque[float]] = {
    "add_candle_data": deque(maxlen=360),
    "add_book_tickers": deque(maxlen=1280),
    "add_mark_price": deque(maxlen=10),
    "add_aggregate_trades": deque(maxlen=1280),
    "collector_organize_data": deque(maxlen=60),
    "perform_transaction": deque(maxlen=360),
    "display_transaction_lines": deque(maxlen=20),
}


def add_task_duration(task_name, duration):
    task_durations[task_name].append(duration)


def get_task_duration() -> dict[str, deque[float]]:
    return task_durations


def to_moment(exact_time: datetime) -> datetime:
    """
    In Solie's terminlogy, moment refers to a time on a 10-second unit.
    This is because one candlestick holds 10 seconds of information.
    """
    moment = exact_time.replace(microsecond=0)
    moment = moment - timedelta(seconds=moment.second % 10)
    return moment
