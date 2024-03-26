from collections import deque

task_durations = {
    "add_candle_data": deque(maxlen=360),
    "add_book_tickers": deque(maxlen=1280),
    "add_mark_price": deque(maxlen=10),
    "add_aggregate_trades": deque(maxlen=1280),
    "collector_organize_data": deque(maxlen=60),
    "perform_transaction": deque(maxlen=360),
    "display_light_transaction_lines": deque(maxlen=60),
    "display_all_transaction_lines": deque(maxlen=20),
}


def add(task_name, duration):
    task_durations[task_name].append(duration)


def get():
    return task_durations
