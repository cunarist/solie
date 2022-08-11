import multiprocessing
import logging
import time
import os

import dill

from module import thread_toss

_communication_manager = None
_task_presences = None
_pool = None
_pool_process_count = 0

_is_task_present = False


def _error_callback(error):
    try:
        raise error
    except Exception:  # noqa:B902
        logger = logging.getLogger("solsol")
        logger.exception("Exception occured from the process pool")


def _process_arguments(payload):
    global _is_task_present
    _is_task_present = True
    function, args, kwargs = dill.loads(payload)
    try:
        returned = function(*args, **kwargs)
        _is_task_present = False
    except Exception as error:  # noqa:B902
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
    except Exception as error:  # noqa:B902
        _is_task_present = False
        raise error
    returned = function(item)
    return returned


def _start_sharing_task_presence(shared_dictionary):
    def job():
        while True:
            process_id = multiprocessing.current_process().pid
            shared_dictionary[process_id] = _is_task_present
            time.sleep(0.1)

    thread_toss.apply_async(job)


def start_pool():
    global _communication_manager
    global _task_presences
    global _pool
    global _pool_process_count
    _pool_process_count = os.cpu_count()
    _communication_manager = multiprocessing.Manager()
    _task_presences = _communication_manager.dict()
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
    for process_id, thread_count in _task_presences.items():
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
