from asyncio import Task, create_task
from typing import Coroutine, TypeVar

T = TypeVar("T")

# A set to keep track of all running tasks.
all_tasks = set[Task]()


def spawn(coroutine: Coroutine[None, None, T]) -> Task[T]:
    """
    Spawns an asynchronous task from the given coroutine and manages its lifecycle.

    This function creates a new `asyncio.Task` from the provided coroutine and
    adds it to a global set to maintain a strong reference. This
    prevents the task from being prematurely garbage-collected by the event loop.

    Once the task completes, it automatically removes itself from the set to
    avoid memory leaks.
    """

    task = create_task(coroutine)

    # Add task to the set. This creates a strong reference.
    # Per the `asyncio` documentation,
    # the event loop only retains a weak reference to tasks.
    # If the task returned by `asyncio.create_task` and
    # `asyncio.ensure_future` is not stored in
    # a variable, or a collection, or otherwise referenced,
    # it may be garbage collected at any time.
    # This can lead to unexpected and inconsistent behavior.
    all_tasks.add(task)

    # To prevent keeping references to finished tasks forever,
    # make each task remove its own reference
    # from the set after completion.
    task.add_done_callback(all_tasks.discard)

    return task
