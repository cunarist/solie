import asyncio
import functools
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")


def prepare():
    global process_count
    global process_pool
    global communicator

    # Use only half of the cores
    # as stuffing all the cores with tasks leads to a system slowdown.
    process_count = multiprocessing.cpu_count()
    process_pool = ProcessPoolExecutor(process_count)
    communicator = multiprocessing.Manager()


async def go(callable: Callable[..., T], *args, **kwargs) -> T:
    """
    Executes the given callable in a separate process pool
    using `asyncio`'s `run_in_executor`.
    This function is intended for executing blocking or CPU-bound operations
    asynchronously outside `asyncio`'s event loop.

    Example:
    ```
    # Define a blocking function
    def my_blocking_function(a, b):
        for _ in range(100000):
            pass
        return a + b

    # Call the blocking function asynchronously using go
    result = await go(my_blocking_function, 10, 20)
    print(result)  # Output: 30
    ```
    """
    event_loop = asyncio.get_event_loop()
    result = await event_loop.run_in_executor(
        process_pool,
        functools.partial(
            callable,
            *args,
            **kwargs,
        ),
    )
    return result
