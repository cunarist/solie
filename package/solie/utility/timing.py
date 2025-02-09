from collections import deque
from datetime import datetime, timedelta
from time import time
from typing import NamedTuple


class DurationRecord(NamedTuple):
    duration: float
    written_at: float


task_durations: dict[str, deque[DurationRecord]] = {}


def add_task_duration(task_name: str, duration: float):
    # Get the deque.
    record_deque = task_durations.get(task_name)
    if record_deque is None:
        record_deque = deque[DurationRecord](maxlen=1024)
        task_durations[task_name] = record_deque

    # Add the record.
    duration_record = DurationRecord(
        duration=duration,
        written_at=time(),
    )
    record_deque.append(duration_record)

    # Remove items that are more than a minute old.
    preserve_from = time() - 60.0
    while record_deque and record_deque[0][1] < preserve_from:
        record_deque.popleft()


def get_task_durations() -> dict[str, list[float]]:
    dict_durations = {k: [r[0] for r in d] for k, d in task_durations.items()}
    return dict_durations


def to_moment(exact_time: datetime) -> datetime:
    """
    In Solie's terminlogy, moment refers to a time on a 10-second unit.
    This is because one candlestick holds 10 seconds of information.
    """
    moment = exact_time.replace(microsecond=0)
    moment = moment - timedelta(seconds=moment.second % 10)
    return moment
