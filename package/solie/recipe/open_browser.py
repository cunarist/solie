import webbrowser

import solie


def do(url: str):
    solie.event_loop.run_in_executor(None, webbrowser.open, url)
