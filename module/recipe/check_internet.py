import time
import socket
import threading
import logging

from module.recipe import thread_toss

_IS_READY = threading.Event()
_WAS_CONNECTED = False
_CONNECTED_FUNCTIONS = []
_DISCONNECTED_FUNCTIONS = []


def connected():
    if _IS_READY.is_set():
        return _WAS_CONNECTED
    else:
        raise RuntimeError("Internet connection is not being monitored")


def start_monitoring():
    def job():
        global _WAS_CONNECTED
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
            if _WAS_CONNECTED and not is_connected:
                for job in _DISCONNECTED_FUNCTIONS:
                    thread_toss.apply_async(job)
                logging.getLogger("solsol").warning("Internet disconnected")
            elif not _WAS_CONNECTED and is_connected:
                for job in _CONNECTED_FUNCTIONS:
                    thread_toss.apply_async(job)
                logging.getLogger("solsol").info("Internet connected")
            # remember connection state
            _WAS_CONNECTED = is_connected
            _IS_READY.set()
            # wait for a while
            time.sleep(0.1)

    thread_toss.apply_async(job)
    _IS_READY.wait()


def add_connected_functions(job_list):
    global _CONNECTED_FUNCTIONS
    _CONNECTED_FUNCTIONS += job_list


def add_disconnected_functions(job_list):
    global _DISCONNECTED_FUNCTIONS
    _DISCONNECTED_FUNCTIONS += job_list
