import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone

import aiofiles

from module import core
from module.shelf.long_text_view import LongTextView


class LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()

        self.executed_time = datetime.now(timezone.utc).replace(microsecond=0)

        log_format = "%(asctime)s.%(msecs)03d %(levelname)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        log_formatter = logging.Formatter(log_format, datefmt=date_format)
        log_formatter.converter = time.gmtime
        self.setFormatter(log_formatter)

        os.makedirs("./logs", exist_ok=True)

    def emit(self, log_record: logging.LogRecord):
        formatted = self.format(log_record)

        # when this is from exception
        if log_record.exc_info is not None:
            lines = formatted.split("\n")
            summarization = lines[0]
            log_content = "\n".join(lines[1:])
            exception = log_record.exc_info[0]
            if exception is None:
                return
            exc_type = exception.__name__
            summarization += f" - {exc_type}"
        # when this is a normal log
        else:
            summarization = formatted
            log_content = log_record.getMessage()
            first_line_content = log_content.split("\n")[0].strip()
            summarization += f" - {first_line_content}"
            summarization = summarization[:80]

        if not core.app_close_event.is_set():
            if core.window.should_overlap_error:

                async def job(log_content=log_content):
                    formation = [
                        "There was an error",
                        LongTextView,
                        False,
                        [log_content],
                    ]
                    await core.window.overlap(formation)

                asyncio.create_task(job())

            else:
                asyncio.create_task(
                    self.add_log_output(
                        summarization,
                        log_content,
                    ),
                )
        else:
            sys.stdout.write(log_content)

    async def add_log_output(self, *args, **kwargs):
        # get the data
        summarization = args[0]
        log_content = args[1]

        # add to log list
        core.window.listWidget.addItem(summarization, log_content)

        # save to file
        task_start_time = datetime.now(timezone.utc)
        filename = str(self.executed_time)
        filename = filename.replace(":", "_")
        filename = filename.replace(" ", "_")
        filename = filename.replace("-", "_")
        filename = filename.replace("+", "_")
        filename = f"./logs/{filename}.txt"
        async with aiofiles.open(filename, "a", encoding="utf8") as file:
            await file.write(f"{summarization}\n")
            await file.write(f"{log_content}\n\n")
        duration = datetime.now(timezone.utc) - task_start_time
        duration = duration.total_seconds()
