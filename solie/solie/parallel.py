import functools
import multiprocessing
from asyncio import AbstractEventLoop
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")


def prepare(event_loop_received: AbstractEventLoop):
    global event_loop
    global process_count
    global process_pool
    global communicator

    event_loop = event_loop_received
    process_count = multiprocessing.cpu_count()
    process_pool = ProcessPoolExecutor(process_count)
    communicator = multiprocessing.Manager()


async def go(callable: Callable[..., T], *args, **kwargs) -> T:
    """
    Executes the given callable in a separate process pool
    using `asyncio`'s `run_in_executor`.
    This function is intended for executing blocking or CPU-bound operations
    asynchronously inside asyncio's event loop.

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
    return await event_loop.run_in_executor(
        process_pool,
        functools.partial(
            callable,
            *args,
            **kwargs,
        ),
    )
