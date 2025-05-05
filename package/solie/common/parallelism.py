import functools
from asyncio import get_event_loop
from collections.abc import Callable
from concurrent.futures import BrokenExecutor, ProcessPoolExecutor
from multiprocessing import Manager, cpu_count
from multiprocessing.managers import SyncManager
from typing import ClassVar

PROCESS_COUNT = cpu_count()


class PoolHolder:
    process_pool: ClassVar[ProcessPoolExecutor]
    sync_manager: ClassVar[SyncManager]


def prepare_process_pool():
    PoolHolder.process_pool = ProcessPoolExecutor(PROCESS_COUNT)
    PoolHolder.sync_manager = Manager()


def shutdown_process_pool():
    PoolHolder.process_pool.shutdown()
    PoolHolder.sync_manager.shutdown()


def get_sync_manager() -> SyncManager:
    return PoolHolder.sync_manager


async def spawn_blocking[**P, T](
    callable: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """
    Executes the given callable in a separate process pool
    using `asyncio`'s `run_in_executor`.
    This function is intended for executing blocking or CPU-bound operations
    asynchronously outside `asyncio`'s event loop.

    Example:
    ```python
    # Define a blocking function
    def my_blocking_function(a, b):
        for _ in range(1000000):
            pass
        return a + b

    # Call the blocking function asynchronously using go
    result = await go(my_blocking_function, 10, 20)
    print(result)  # Output: 30
    ```
    """
    process_pool = PoolHolder.process_pool
    event_loop = get_event_loop()
    partial_callable = functools.partial(callable, *args, **kwargs)
    try:
        result = await event_loop.run_in_executor(process_pool, partial_callable)
    except BrokenExecutor:
        shutdown_process_pool()
        prepare_process_pool()
        result = await event_loop.run_in_executor(process_pool, partial_callable)
    return result
