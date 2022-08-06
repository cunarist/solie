import time
import socket
import threading
import logging

from module import thread_toss

_is_ready = threading.Event()
_was_connected = False
_connected_functions = []
_disconnected_functions = []


def connected():
    if _is_ready.is_set():
        return _was_connected
    else:
        raise RuntimeError("Internet connection is not being monitored")


def start_monitoring():
    def job():
        global _was_connected
        while True:
            # try to connect to DNS servers
            attempt_ips = (
                "1.0.0.1",  # Cloudflare
                "1.1.1.1",  # Cloudflare
                "8.8.4.4",  # Google
                "8.8.8.8",  # Google
                "9.9.9.9",  # Quad9
                "149.112.112.112",  # Quad9
                "208.67.222.222",  # OpenDNS
                "208.67.220.220",  # OpenDNS
            )
            is_connected = False
            for attempt_ip in attempt_ips:
                try:
                    socket.create_connection((attempt_ip, 53))
                    is_connected = True
                    break
                except OSError:
                    pass
            # detect changes
            if _was_connected and not is_connected:
                for job in _disconnected_functions:
                    thread_toss.apply_async(job)
                logging.getLogger("solsol").warning("Internet disconnected")
            elif not _was_connected and is_connected:
                for job in _connected_functions:
                    thread_toss.apply_async(job)
                logging.getLogger("solsol").info("Internet connected")
            # remember connection state
            _was_connected = is_connected
            _is_ready.set()
            # wait for a while
            time.sleep(0.1)

    thread_toss.apply_async(job)
    _is_ready.wait()


def add_connected_functions(job_list):
    global _connected_functions
    _connected_functions += job_list


def add_disconnected_functions(job_list):
    global _disconnected_functions
    _disconnected_functions += job_list
