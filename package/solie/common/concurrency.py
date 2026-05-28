"""Asynchronous task management and concurrency utilities."""

from asyncio import CancelledError, Task, create_task, wait_for
from collections.abc import Callable, Coroutine
from types import TracebackType
from typing import Any, Self

# A set to keep track of all running tasks.
all_tasks = set[Task[Any]]()


def spawn[T](coroutine: Coroutine[None, None, T]) -> Task[T]:
    """Spawns an asynchronous task from the given coroutine and manages its lifecycle.

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
    """A class to manage spawning unique async tasks.

    Ensures only the latest task is running.
    """

    def __init__(self) -> None:
        """Initialize the unique task manager."""
        self._task: Task[Any] | None = None

    async def __aenter__(self) -> Self:
        """Enter the unique-task resource scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Cancel the owned task when leaving the scope."""
        del exc_type, exc, traceback
        await self._cancel_and_wait()

    def spawn(self, coro: Coroutine[None, None, Any]) -> None:
        """Spawns a new task, canceling the previous one if it exists."""
        self.cancel()
        self._task = spawn(coro)

    def cancel(self) -> None:
        """Cancel the previous task if it exists."""
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _cancel_and_wait(self, wait_seconds: float = 2.0) -> None:
        """Cancel the previous task and briefly wait for cleanup."""
        task = self._task
        self.cancel()
        if task is None or task.done():
            return
        try:
            await wait_for(task, timeout=wait_seconds)
        except (CancelledError, TimeoutError):
            pass

    def add_done_callback(self, callback: Callable[[Task[Any]], Any]) -> None:
        """Add a callback to be called when the current task is done."""
        if self._task is not None:
            self._task.add_done_callback(callback)
