from asyncio import Task, create_task
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")

# A set to keep track of all running tasks.
all_tasks = set[Task[Any]]()


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


class UniqueTask:
    """
    A class to manage spawning unique async tasks,
    ensuring only the latest one is running.
    """

    def __init__(self):
        self._task: Task[Any] | None = None

    def spawn(self, coro: Coroutine[None, None, Any]):
        """
        Spawns a new task, canceling the previous one if it exists.
        """
        self.cancel()
        self._task = create_task(coro)

    def cancel(self):
        """Cancels the previous task if it exists."""
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def add_done_callback(self, callback: Callable[[Task[Any]], Any]):
        """
        Adds a callback to be called when the current task is done.
        """
        if self._task is not None:
            self._task.add_done_callback(callback)
