from multiprocessing.pool import ThreadPool
import logging
import threading

_pool = ThreadPool(64)


def _error_callback(error):
    try:
        raise error
    except Exception:
        logger = logging.getLogger("solsol")
        logger.exception("Exception occured from the thread pool")


def _process_arguments(payload):
    threading.currentThread().is_task_present = True
    function, args, kwargs = payload
    try:
        returned = function(*args, **kwargs)
        threading.currentThread().is_task_present = False
    except Exception as error:
        threading.currentThread().is_task_present = False
        raise error
    return returned


def _process_iterable_item(payload):
    threading.currentThread().is_task_present = True
    function, item = payload
    try:
        returned = function(item)
        threading.currentThread().is_task_present = False
    except Exception as error:
        threading.currentThread().is_task_present = False
        raise error
    return returned


def get_task_presences():
    return_dictionary = {}
    for thread in _pool._pool:
        task_presence = getattr(thread, "is_task_present", False)
        return_dictionary[thread.name] = task_presence
    return return_dictionary


def apply(function, *args, **kwargs):
    payload = (function, args, kwargs)
    returned = _pool.apply(_process_arguments, (payload,))
    return returned


def apply_async(function, *args, **kwargs):
    payload = (function, args, kwargs)
    returned = _pool.apply_async(
        _process_arguments,
        (payload,),
        error_callback=_error_callback,
    )
    return returned


def map(function, iterable):
    wrapper = [(function, item) for item in iterable]
    returned = _pool.map(_process_iterable_item, wrapper)
    return returned


def map_async(function, iterable):
    wrapper = [(function, item) for item in iterable]
    returned = _pool.map_async(
        _process_iterable_item,
        wrapper,
        error_callback=_error_callback,
    )
    return returned
