"""Read-write lock implementation for async operations."""

import types
from asyncio import (
    AbstractEventLoop,
    CancelledError,
    Future,
    Task,
    current_task,
    get_running_loop,
    sleep,
)
from collections import deque
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


class NoTaskError(Exception):
    """Exception raised when no current task is found."""

    def __init__(self) -> None:
        """Initialize NoTaskError with message."""
        super().__init__("Cannot acquire lock outside of a task")


class LockUpgradeError(Exception):
    """Exception raised when attempting to upgrade from read to write lock."""

    def __init__(self) -> None:
        """Initialize LockUpgradeError with message."""
        super().__init__("Cannot upgrade RWLock from read to write")


class LockReleaseError(Exception):
    """Exception raised when attempting to release an un-acquired lock."""

    def __init__(self) -> None:
        """Initialize LockReleaseError with message."""
        super().__init__("Cannot release an un-acquired lock")


# The internal lock object managing the RWLock state.
class RWLockCore:
    """Core read-write lock implementation."""

    _RL = 1
    _WL = 2

    def __init__(self, fast: bool, loop: AbstractEventLoop) -> None:
        """Initialize RWLock core."""
        self._do_yield = not fast
        self._loop = loop
        self._read_waiters = deque[Future[None]]()
        self._write_waiters = deque[Future[None]]()
        self._r_state: int = 0
        self._w_state: int = 0
        # tasks will be few, so a list is not inefficient
        self._owning: list[tuple[Task[Any], int]] = []

    @property
    def r_state(self) -> int:
        """Get read lock state count."""
        return self._r_state

    @property
    def w_state(self) -> int:
        """Get write lock state count."""
        return self._w_state

    @property
    def read_locked(self) -> bool:
        """Check if read lock is held."""
        return self._r_state > 0

    @property
    def write_locked(self) -> bool:
        """Check if write lock is held."""
        return self._w_state > 0

    async def _yield_after_acquire(self, lock_type: int) -> None:
        if self._do_yield:
            try:
                await sleep(0.0)
            except CancelledError:
                self._release(lock_type)
                self._wake_up()
                raise

    # Acquire the lock in read mode.
    async def acquire_read(self) -> bool:
        """Acquire lock in read mode."""
        me = current_task()
        if me is None:
            raise NoTaskError

        if (me, self._RL) in self._owning or (me, self._WL) in self._owning:
            self._r_state += 1
            self._owning.append((me, self._RL))
            await self._yield_after_acquire(self._RL)
            return True

        if not self._write_waiters and self._r_state >= 0 and self._w_state == 0:
            self._r_state += 1
            self._owning.append((me, self._RL))
            await self._yield_after_acquire(self._RL)
            return True

        fut = self._loop.create_future()
        self._read_waiters.append(fut)
        try:
            await fut
            self._owning.append((me, self._RL))
            return True

        except CancelledError:
            self._r_state -= 1
            self._wake_up()
            raise

        finally:
            self._read_waiters.remove(fut)

    # Acquire the lock in write mode.  A 'waiting' count is maintained,
    # ensuring that 'readers' will yield to writers.
    async def acquire_write(self) -> bool:
        """Acquire lock in write mode."""
        me = current_task()
        if me is None:
            raise NoTaskError
        if (me, self._WL) in self._owning:
            self._w_state += 1
            self._owning.append((me, self._WL))
            await self._yield_after_acquire(self._WL)
            return True
        if (me, self._RL) in self._owning and self._r_state > 0:
            raise LockUpgradeError

        if self._r_state == 0 and self._w_state == 0:
            self._w_state += 1
            self._owning.append((me, self._WL))
            await self._yield_after_acquire(self._WL)
            return True

        fut = self._loop.create_future()
        self._write_waiters.append(fut)
        try:
            await fut
            self._owning.append((me, self._WL))
            return True

        except CancelledError:
            self._w_state -= 1
            self._wake_up()
            raise

        finally:
            self._write_waiters.remove(fut)

    def release_read(self) -> None:
        """Release read lock."""
        self._release(self._RL)

    def release_write(self) -> None:
        """Release write lock."""
        self._release(self._WL)

    def _release(self, lock_type: int) -> None:
        me = current_task(loop=self._loop)
        if me is None:
            raise NoTaskError
        try:
            self._owning.remove((me, lock_type))
        except ValueError as err:
            raise LockReleaseError from err
        if lock_type == self._RL:
            self._r_state -= 1
        else:
            self._w_state -= 1
        self._wake_up()

    def _wake_up(self) -> None:
        # If no one is reading or writing, wake up write waiters
        # first, only one write waiter should be waken up, if no
        # write waiters and have read waiters, wake up all read
        # waiters.
        if self._r_state == 0 and self._w_state == 0:
            if self._write_waiters:
                # Wake up the first waiter which isn't cancelled.
                for fut in self._write_waiters:
                    if not fut.done():
                        fut.set_result(None)
                        self._w_state += 1
                        return

            # Wake up all not cancelled waiters.
            for fut in self._read_waiters:
                if not fut.done():
                    fut.set_result(None)
                    self._r_state += 1


class Cell[T]:
    """Mutable cell holding data protected by RWLock."""

    def __init__(self, data: T) -> None:
        """Initialize cell with data."""
        self.data: T = data


# Lock objects to access the _RWLockCore in reader or writer mode
class ReadLock[T]:
    """Read lock for shared access to data."""

    def __init__(self, lock: RWLockCore, wrapper: Cell[T]) -> None:
        """Initialize read lock."""
        self._wrapper = wrapper
        self._lock = lock

    @property
    def locked(self) -> bool:
        """Check if read lock is held."""
        return self._lock.read_locked

    async def __aenter__(self) -> Cell[T]:
        """Acquire read lock on enter."""
        await self._lock.acquire_read()
        return self._wrapper

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None:
        """Release read lock on exit."""
        self._lock.release_read()

    def __repr__(self) -> str:
        """Return string representation of read lock."""
        status = "locked" if self._lock.r_state > 0 else "unlocked"
        return f"<ReaderLock: [{status}]>"


class WriteLock[T]:
    """Write lock for exclusive access to data."""

    def __init__(self, lock: RWLockCore, wrapper: Cell[T]) -> None:
        """Initialize write lock."""
        self._wrapper = wrapper
        self._lock = lock

    @property
    def locked(self) -> bool:
        """Check if write lock is held."""
        return self._lock.write_locked

    async def __aenter__(self) -> Cell[T]:
        """Acquire write lock on enter."""
        await self._lock.acquire_write()
        return self._wrapper

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None:
        """Release write lock on exit."""
        self._lock.release_write()

    def __repr__(self) -> str:
        """Return string representation of write lock."""
        status = "locked" if self._lock.w_state > 0 else "unlocked"
        return f"<WriterLock: [{status}]>"


class RWLock[T]:
    """Read-write lock for concurrent access control.

    A RWLock maintains a pair of associated locks, one for read-only
    operations and one for writing. The read lock may be held simultaneously
    by multiple reader tasks, so long as there are no writers. The write
    lock is exclusive.
    """

    def __init__(self, cell_data: T, fast: bool = True) -> None:
        """Initialize read-write lock."""
        loop = get_running_loop()
        self._wrapper = Cell(cell_data)
        self._loop = loop
        core = RWLockCore(fast, self._loop)
        self.read_lock = ReadLock(core, self._wrapper)
        self.write_lock = WriteLock(core, self._wrapper)

    def __repr__(self) -> str:
        """Return string representation of RWLock."""
        rl = self.read_lock.__repr__()
        wl = self.write_lock.__repr__()
        return f"<RWLock: {rl} {wl}>"

    def replace(self, new: T) -> None:
        """Replace data in cell."""
        self._wrapped = new
