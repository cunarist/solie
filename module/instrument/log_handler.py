import logging
import time

from module import core
from module import thread_toss
from module.worker import manager
from module.shelf.long_text_view import LongTextView


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
        lines = formatted.split("\n")

        if len(lines) > 1:
            summarization = lines[0]
            log_content = "\n".join(lines[1:])
        else:
            summarization = formatted
            log_content = log_record.getMessage()

        if log_record.exc_info is None:
            plain_message = log_content.split("\n")[0]
            summarization += f" - {plain_message}"
        else:
            exc_type = log_record.exc_info[0].__name__
            summarization += f" - {exc_type}"

        summarization = summarization[:60]

        if core.window.should_overlap_error:

            def job(log_content=log_content):
                formation = [
                    "There was an error",
                    LongTextView,
                    False,
                    [log_content],
                ]
                core.window.overlap(formation)

            thread_toss.apply_async(job)

        else:
            manager.me.add_log_output(summarization, log_content)
