import multiprocessing
import logging
import threading
import time

import dill

from module.recipe import thread_toss

_COMMUNICATION_MANAGER = None
_THREAD_COUNTS = None
_POOL = None
_POOL_PROCESS_COUNT = 0


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
    global _COMMUNICATION_MANAGER
    global _THREAD_COUNTS
    global _POOL
    global _POOL_PROCESS_COUNT
    cpu_count = multiprocessing.cpu_count()
    pool_process_count = int(cpu_count / 2)
    _COMMUNICATION_MANAGER = multiprocessing.Manager()
    _THREAD_COUNTS = _COMMUNICATION_MANAGER.dict()
    _POOL = multiprocessing.Pool(
        pool_process_count,
        initializer=_start_sharing_thread_count,
        initargs=(_THREAD_COUNTS,),
    )
    _POOL_PROCESS_COUNT = pool_process_count
    _start_sharing_thread_count(_THREAD_COUNTS)


def terminate_pool():
    _POOL.terminate()
    _POOL.join()


def get_thread_counts():
    return_dictionary = {}
    for process_id, thread_count in _THREAD_COUNTS.items():
        return_dictionary[process_id] = thread_count
    return return_dictionary


def get_pool_process_count():
    return _POOL_PROCESS_COUNT


def apply(function, *args, **kwargs):
    payload = dill.dumps((function, args, kwargs))
    returned = _POOL.apply(_process_arguments, (payload,))
    return returned


def apply_async(function, *args, **kwargs):
    payload = dill.dumps((function, args, kwargs))
    returned = _POOL.apply_async(
        _process_arguments,
        (payload,),
        error_callback=_error_callback,
    )
    return returned


def map(function, iterable):
    wrapper = [dill.dumps((function, item)) for item in iterable]
    returned = _POOL.map(_process_iterable_item, wrapper)
    return returned


def map_async(function, iterable):
    wrapper = [dill.dumps((function, item)) for item in iterable]
    returned = _POOL.map_async(
        _process_iterable_item,
        wrapper,
        error_callback=_error_callback,
    )
    return returned
