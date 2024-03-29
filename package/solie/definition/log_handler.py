import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

import solie


class LogHandler(logging.Handler):
    def __init__(self, log_path: Path):
        super().__init__()

        os.makedirs(log_path, exist_ok=True)
        self.log_path = log_path

        log_format = "%(asctime)s.%(msecs)03d %(levelname)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        log_formatter = logging.Formatter(log_format, datefmt=date_format)
        log_formatter.converter = time.gmtime
        self.setFormatter(log_formatter)

        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.filename = (
            f"{now.year:04}-{now.month:02}-{now.day:02}"
            + f".{now.hour:02}-{now.minute:02}-{now.second:02}"
            + f".{now.tzinfo}.txt"
        )

    def emit(self, log_record: logging.LogRecord):
        formatted = self.format(log_record)

        if log_record.exc_info is not None:
            # when this is from an exception
            lines = formatted.split("\n")
            summarization = lines[0]
            log_content = "\n".join(lines[1:])
            exception = log_record.exc_info[0]
            if exception is None:
                return
            exc_type = exception.__name__
            summarization += f" - {exc_type}"
        else:
            # when this is a normal log
            summarization = formatted
            log_content = log_record.getMessage()
            first_line_content = log_content.split("\n")[0].strip()
            summarization += f" - {first_line_content}"
            summarization = summarization[:80]

        asyncio.create_task(
            self.add_log_output(
                summarization,
                log_content,
            )
        )

    async def add_log_output(self, *args, **kwargs):
        # get the data
        summarization = args[0]
        log_content = args[1]

        # add to log list
        solie.window.listWidget.addItem(summarization, log_content)

        # save to file
        filepath = self.log_path / self.filename
        async with aiofiles.open(filepath, "a", encoding="utf8") as file:
            await file.write(f"{summarization}\n")
            await file.write(f"{log_content}\n\n")
