import socket
import logging
import asyncio


is_ready = asyncio.Event()
_was_connected = False
_connected_functions = []
_disconnected_functions = []


def connected():
    if is_ready.is_set():
        return _was_connected
    else:
        raise RuntimeError("Internet connection is not being monitored")


async def monitor():
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
                asyncio.create_task(job())
            logging.getLogger("solie").warning("Internet disconnected")
        elif not _was_connected and is_connected:
            for job in _connected_functions:
                asyncio.create_task(job())
            logging.getLogger("solie").info("Internet connected")
        # remember connection state
        _was_connected = is_connected
        is_ready.set()
        # wait for a while
        await asyncio.sleep(1)


def add_connected_functions(job_list):
    global _connected_functions
    _connected_functions += job_list


def add_disconnected_functions(job_list):
    global _disconnected_functions
    _disconnected_functions += job_list
