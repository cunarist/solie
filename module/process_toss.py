import multiprocessing
import logging
import threading
import time
import os

import dill

from module import thread_toss

_communication_manager = None
_thread_counts = None
_pool = None
_pool_process_count = 0


def _error_callback(error):
    try:
        raise error
    except Exception:  # noqa:B902
        logger = logging.getLogger("solsol")
        logger.exception("Exception occured from the process pool")


def _start_sharing_thread_count(shared_dictionary):
    def job():
        while True:
            process_id = multiprocessing.current_process().pid
            thread_count = threading.active_count()
            shared_dictionary[process_id] = thread_count
            time.sleep(0.1)

    thread_toss.apply_async(job)


def _process_arguments(payload):
    function, args, kwargs = dill.loads(payload)
    returned = function(*args, **kwargs)
    return returned


def _process_iterable_item(payload):
    function, item = dill.loads(payload)
    returned = function(item)
    return returned


def start_pool():
    global _communication_manager
    global _thread_counts
    global _pool
    global _pool_process_count
    _pool_process_count = os.cpu_count()
    _communication_manager = multiprocessing.Manager()
    _thread_counts = _communication_manager.dict()
    _pool = multiprocessing.Pool(
        _pool_process_count,
        initializer=_start_sharing_thread_count,
        initargs=(_thread_counts,),
    )
    _start_sharing_thread_count(_thread_counts)


def terminate_pool():
    _pool.terminate()
    _pool.join()


def get_thread_counts():
    return_dictionary = {}
    for process_id, thread_count in _thread_counts.items():
        return_dictionary[process_id] = thread_count
    return return_dictionary


def get_pool_process_count():
    return _pool_process_count


def apply(function, *args, **kwargs):
    payload = dill.dumps((function, args, kwargs))
    returned = _pool.apply(_process_arguments, (payload,))
    return returned


def apply_async(function, *args, **kwargs):
    payload = dill.dumps((function, args, kwargs))
    returned = _pool.apply_async(
        _process_arguments,
        (payload,),
        error_callback=_error_callback,
    )
    return returned


def map(function, iterable):
    wrapper = [dill.dumps((function, item)) for item in iterable]
    returned = _pool.map(_process_iterable_item, wrapper)
    return returned


def map_async(function, iterable):
    wrapper = [dill.dumps((function, item)) for item in iterable]
    returned = _pool.map_async(
        _process_iterable_item,
        wrapper,
        error_callback=_error_callback,
    )
    return returned
