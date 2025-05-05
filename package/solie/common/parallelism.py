import functools
from asyncio import get_event_loop
from collections.abc import Callable
from concurrent.futures import BrokenExecutor, ProcessPoolExecutor
from multiprocessing import Manager, cpu_count
from multiprocessing.managers import SyncManager

PROCESS_COUNT = cpu_count()
sync_manager: SyncManager | None = None


def prepare_process_pool():
    global process_pool
    process_pool = ProcessPoolExecutor(PROCESS_COUNT)


def get_sync_manager() -> SyncManager:
    global sync_manager
    if sync_manager is None:
        sync_manager = Manager()
    return sync_manager


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
    event_loop = get_event_loop()
    try:
        result = await event_loop.run_in_executor(
            process_pool,
            functools.partial(callable, *args, **kwargs),
        )
    except BrokenExecutor:
        process_pool.shutdown()
        prepare_process_pool()
        result = await event_loop.run_in_executor(
            process_pool,
            functools.partial(callable, *args, **kwargs),
        )
    return result
