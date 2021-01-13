import logging


class LogHandler(logging.Handler):
    def __init__(self, after_function):
        super().__init__()
        self.after_function = after_function

    def emit(self, log_record):
        log_message = self.format(log_record)
        self.after_function(log_message)
