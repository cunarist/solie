import logging
import time

from module import core
from module import thread_toss
from module.worker import manager
from module.shelf.full_log_view import FullLogView


class LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        log_format = "%(asctime)s.%(msecs)03d %(levelname)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        log_formatter = logging.Formatter(log_format, datefmt=date_format)
        log_formatter.converter = time.gmtime
        self.setFormatter(log_formatter)

    def emit(self, log_record):
        text = self.format(log_record)
        lines = text.split("\n")
        message = log_record.getMessage()
        if log_record.exc_info is None:
            plain_message = message.split("\n")[0]
            lines[0] += f" - {plain_message}"
        else:
            exc_type = log_record.exc_info[0].__name__
            lines[0] += f" - {exc_type}"
        lines.insert(1, message)
        lines[0] = lines[0][:80]
        text = "\n".join(lines)

        if core.window.should_overlap_error:

            def job(text=text):
                formation = [
                    "There was an error",
                    FullLogView,
                    False,
                    [text],
                ]
                core.window.overlap(formation)

        else:

            def job(text=text):
                manager.me.add_log_output(text)

        thread_toss.apply_async(job)
