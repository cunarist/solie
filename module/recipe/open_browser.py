import webbrowser

from module import core


def do(url: str):
    core.event_loop.run_in_executor(None, webbrowser.open, url)
