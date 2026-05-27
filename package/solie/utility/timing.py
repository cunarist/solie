"""Performance timing and duration recording utilities."""

from collections import deque
from datetime import datetime, timedelta
from time import perf_counter
from types import TracebackType
from typing import NamedTuple, Self


class DurationRecord(NamedTuple):
    """Record of task duration with timestamp."""

    duration: float
    written_at: float


type DurationRecords = dict[str, deque[DurationRecord]]


class DurationRecorder:
    """Records and tracks task execution durations."""

    def __init__(self, task_name: str, records: DurationRecords) -> None:
        """Initialize duration recorder."""
        self._task_name = task_name
        self._records = records
        self._start_time = perf_counter()
        self._did_record = False

    def __enter__(self) -> Self:
        """Enter duration measurement."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Record elapsed time."""
        del exc_type, exc, traceback
        self._record()

    def _record(self) -> None:
        """Record task completion time."""
        # Check that this is the first time.
        if self._did_record:
            msg = "Cannot record more than once"
            raise RuntimeError(msg)
        self._did_record = True

        # Get the task name and current time.
        task_name = self._task_name
        now_time = perf_counter()

        # Get the deque.
        record_deque = self._records.get(task_name)
        if record_deque is None:
            record_deque = deque[DurationRecord](maxlen=1024)
            self._records[task_name] = record_deque

        # Add the record.
        duration_record = DurationRecord(
            duration=now_time - self._start_time,
            written_at=now_time,
        )
        record_deque.append(duration_record)

        # Remove items that are more than a minute old.
        preserve_from = now_time - 60.0
        while record_deque and record_deque[0][1] < preserve_from:
            record_deque.popleft()


def to_moment(exact_time: datetime) -> datetime:
    """Convert exact time to moment (10-second unit).

    In Solie's terminology, moment refers to a time on a 10-second unit.
    This is because one candlestick holds 10 seconds of information.
    """
    moment = exact_time.replace(microsecond=0)
    return moment - timedelta(seconds=moment.second % 10)
