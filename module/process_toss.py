import multiprocessing
import logging
import time
import os

import dill

from module import thread_toss

communicator = None
_task_presences = None
_pool = None
_pool_process_count = 0

_is_task_present = False


def _error_callback(error):
    try:
        raise error
    except Exception:
        logger = logging.getLogger("solsol")
        logger.exception("Exception occured from the process pool")


def _process_arguments(payload):
    global _is_task_present
    _is_task_present = True
    function, args, kwargs = dill.loads(payload)
    try:
        returned = function(*args, **kwargs)
        _is_task_present = False
    except Exception as error:
        _is_task_present = False
        raise error
    return returned


def _process_iterable_item(payload):
    global _is_task_present
    _is_task_present = True
    function, item = dill.loads(payload)
    try:
        returned = function(item)
        _is_task_present = False
    except Exception as error:
        _is_task_present = False
        raise error
    return returned


def _start_sharing_task_presence(received_task_presences):
    def job():
        while True:
            process_id = multiprocessing.current_process().pid
            received_task_presences[process_id] = _is_task_present
            time.sleep(0.1)

    thread_toss.apply_async(job)


def start_pool():
    global communicator
    global _task_presences
    global _pool
    global _pool_process_count
    _pool_process_count = os.cpu_count()
    communicator = multiprocessing.Manager()
    _task_presences = communicator.dict()
    _pool = multiprocessing.Pool(
        _pool_process_count,
        initializer=_start_sharing_task_presence,
        initargs=(_task_presences,),
    )


def terminate_pool():
    _pool.terminate()
    _pool.join()


def get_task_presences():
    return_dictionary = {}
    for process_id, task_presence in _task_presences.items():
        return_dictionary[process_id] = task_presence
    return return_dictionary


def get_pool_process_count():
    return _pool_process_count


def apply(function, *args, **kwargs):
    payload = dill.dumps((function, args, kwargs))
    try:
        returned = _pool.apply(_process_arguments, (payload,))
        return returned
    except Exception:
        logger = logging.getLogger("solsol")
        logger.exception("Exception occured from the process pool")


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
    try:
        returned = _pool.map(_process_iterable_item, wrapper)
        return returned
    except Exception:
        logger = logging.getLogger("solsol")
        logger.exception("Exception occured from the process pool")


def map_async(function, iterable):
    wrapper = [dill.dumps((function, item)) for item in iterable]
    returned = _pool.map_async(
        _process_iterable_item,
        wrapper,
        error_callback=_error_callback,
    )
    return returned
