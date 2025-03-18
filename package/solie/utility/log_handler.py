import time
from asyncio import Lock
from collections.abc import Callable
from datetime import datetime, timezone
from logging import Formatter, Handler
from pathlib import Path

import aiofiles
import aiofiles.os

from solie.common import spawn


class LogHandler(Handler):
    file_lock = Lock()

    def __init__(self, log_path: Path, callback: Callable[[str, str], None]):
        super().__init__()

        self.log_path = log_path
        self.callback = callback

        log_format = "%(asctime)s.%(msecs)03d %(levelname)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        log_formatter = Formatter(log_format, datefmt=date_format)
        log_formatter.converter = time.gmtime
        self.setFormatter(log_formatter)

        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.filename = (
            f"{now.year:04}-{now.month:02}-{now.day:02}"
            + f".{now.hour:02}-{now.minute:02}-{now.second:02}"
            + f".{now.tzinfo}.txt"
        )

    def emit(self, record):
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

        spawn(self.add_log_output(summarization, log_content))

    async def add_log_output(self, summarization: str, log_content: str):
        # add to log list
        self.callback(summarization, log_content)

        # save to file
        filepath = self.log_path / self.filename
        async with self.file_lock:
            async with aiofiles.open(filepath, "a", encoding="utf8") as file:
                line_divider = "-" * 80
                await file.write(f"{log_content}\n\n{line_divider}\n\n")
