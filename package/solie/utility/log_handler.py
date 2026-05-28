"""Custom logging handler."""

import time
from asyncio import Lock, Task, current_task, wait
from collections.abc import Callable
from datetime import UTC, datetime
from logging import Formatter, Handler, LogRecord
from pathlib import Path
from types import TracebackType
from typing import Any, Self, override

import aiofiles

from solie.common import spawn


class LogHandler(Handler):
    """Custom log handler for file and callback."""

    def __init__(self, log_path: Path, callback: Callable[[str, str], None]) -> None:
        """Initialize log handler."""
        super().__init__()

        self.log_path = log_path
        self.callback = callback
        self._file_lock = Lock()
        self._tasks: set[Task[Any]] = set()

        log_format = "%(asctime)s.%(msecs)03d %(levelname)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        log_formatter = Formatter(log_format, datefmt=date_format)
        log_formatter.converter = time.gmtime
        self.setFormatter(log_formatter)

        now = datetime.now(UTC).replace(microsecond=0)
        self.filename = (
            f"{now.year:04}-{now.month:02}-{now.day:02}"
            f".{now.hour:02}-{now.minute:02}-{now.second:02}"
            f".{now.tzinfo}.txt"
        )

    async def __aenter__(self) -> Self:
        """Enter log handler task scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Finish pending log writes."""
        del exc_type, exc, traceback
        await self._close()

    @override
    def emit(self, record: LogRecord) -> None:
        formatted = self.format(record)

        if record.exc_info is not None:
            # when this is from an exception
            lines = formatted.split("\n")
            summarization = lines[0]
            log_content = "\n".join(lines[1:])
            exception = record.exc_info[0]
            if exception is None:
                return
            summarization += f" - {exception.__name__}"
        else:
            # when this is a normal log
            summarization = formatted
            log_content = record.getMessage()
            first_line_content = log_content.split("\n")[0].strip()
            summarization += f" - {first_line_content}"
            summarization = summarization[:80]

        log_content = f"{formatted}\n{log_content}"

        task = spawn(self._add_log_output(summarization, log_content))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _add_log_output(self, summarization: str, log_content: str) -> None:
        # add to log list
        self.callback(summarization, log_content)

        # save to file
        filepath = self.log_path / self.filename
        async with (
            self._file_lock,
            aiofiles.open(filepath, "a", encoding="utf8") as file,
        ):
            line_divider = "-" * 80
            await file.write(f"{log_content}\n\n{line_divider}\n\n")

    async def _close(self) -> None:
        running_task = current_task()
        tasks = [
            task
            for task in self._tasks
            if task is not running_task and not task.done()
        ]
        if len(tasks) == 0:
            self._tasks.clear()
            return
        _, pending = await wait(tasks, timeout=2.0)
        for task in pending:
            task.cancel()
        self._tasks.clear()
