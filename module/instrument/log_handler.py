import asyncio
import logging
import time

from module import core
from module.shelf.long_text_view import LongTextView
from module.worker import manager


class LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        log_format = "%(asctime)s.%(msecs)03d %(levelname)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        log_formatter = logging.Formatter(log_format, datefmt=date_format)
        log_formatter.converter = time.gmtime
        self.setFormatter(log_formatter)

    def emit(self, log_record):
        formatted = self.format(log_record)

        # when this is from exception
        if log_record.exc_info is not None:
            lines = formatted.split("\n")
            summarization = lines[0]
            log_content = "\n".join(lines[1:])
            exc_type = log_record.exc_info[0].__name__
            summarization += f" - {exc_type}"
        # when this is a normal log
        else:
            summarization = formatted
            log_content = log_record.getMessage()
            first_line_content = log_content.split("\n")[0].strip()
            summarization += f" - {first_line_content}"
            summarization = summarization[:80]

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
                manager.me.add_log_output(summarization, log_content),
            )
