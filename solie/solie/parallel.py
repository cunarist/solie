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
    return await event_loop.run_in_executor(
        process_pool,
        functools.partial(
            callable,
            *args,
            **kwargs,
        ),
    )
