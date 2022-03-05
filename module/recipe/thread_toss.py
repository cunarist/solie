from multiprocessing.pool import ThreadPool
import logging

_THREAD_POOL = ThreadPool(64)


def _error_callback(error):
    try:
        raise error
    except Exception:  # noqa:B902
        logger = logging.getLogger("solsol")
        logger.exception("Exception occured from the thread pool")


def apply(function, *args, **kwargs):
    returned = _THREAD_POOL.apply(function, args, kwargs)
    return returned


def apply_async(function, *args, **kwargs):
    returned = _THREAD_POOL.apply_async(
        function,
        args,
        kwargs,
        error_callback=_error_callback,
    )
    return returned


def map(function, iterable):
    returned = _THREAD_POOL.map(function, iterable)
    return returned


def map_async(function, iterable):
    returned = _THREAD_POOL.map_async(
        function,
        iterable,
        error_callback=_error_callback,
    )
    return returned
