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
from typing import Any


# The internal lock object managing the RWLock state.
class RWLockCore:
    _RL = 1
    _WL = 2

    def __init__(self, fast: bool, loop: AbstractEventLoop) -> None:
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
        return self._r_state

    @property
    def w_state(self) -> int:
        return self._w_state

    @property
    def read_locked(self) -> bool:
        return self._r_state > 0

    @property
    def write_locked(self) -> bool:
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
        me = current_task()
        assert me is not None  # nosec

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
        me = current_task()
        assert me is not None  # nosec

        if (me, self._WL) in self._owning:
            self._w_state += 1
            self._owning.append((me, self._WL))
            await self._yield_after_acquire(self._WL)
            return True
        elif (me, self._RL) in self._owning:
            if self._r_state > 0:
                raise RuntimeError("Cannot upgrade RWLock from read to write")

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
        self._release(self._RL)

    def release_write(self) -> None:
        self._release(self._WL)

    def _release(self, lock_type: int) -> None:
        # assert lock_type in (self._RL, self._WL)
        me = current_task(loop=self._loop)
        assert me is not None  # nosec

        try:
            self._owning.remove((me, lock_type))
        except ValueError:
            raise RuntimeError("Cannot release an un-acquired lock")
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
    def __init__(self, data: T) -> None:
        self.data: T = data


# Lock objects to access the _RWLockCore in reader or writer mode
class ReadLock[T]:
    def __init__(self, lock: RWLockCore, wrapper: Cell[T]) -> None:
        self._wrapper = wrapper
        self._lock = lock

    @property
    def locked(self) -> bool:
        return self._lock.read_locked

    async def __aenter__(self) -> Cell[T]:
        await self._lock.acquire_read()
        return self._wrapper

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._lock.release_read()

    def __repr__(self) -> str:
        status = "locked" if self._lock.r_state > 0 else "unlocked"
        return "<ReaderLock: [{}]>".format(status)


class WriteLock[T]:
    def __init__(self, lock: RWLockCore, wrapper: Cell[T]) -> None:
        self._wrapper = wrapper
        self._lock = lock

    @property
    def locked(self) -> bool:
        return self._lock.write_locked

    async def __aenter__(self) -> Cell[T]:
        await self._lock.acquire_write()
        return self._wrapper

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._lock.release_write()

    def __repr__(self) -> str:
        status = "locked" if self._lock.w_state > 0 else "unlocked"
        return "<WriterLock: [{}]>".format(status)


class RWLock[T]:
    """A RWLock maintains a pair of associated locks, one for read-only
    operations and one for writing. The read lock may be held simultaneously
    by multiple reader tasks, so long as there are no writers. The write
    lock is exclusive.
    """

    def __init__(self, cell_data: T, fast: bool = True) -> None:
        loop = get_running_loop()
        self._wrapper = Cell(cell_data)
        self._loop = loop
        core = RWLockCore(fast, self._loop)
        self.read_lock = ReadLock(core, self._wrapper)
        self.write_lock = WriteLock(core, self._wrapper)

    def __repr__(self) -> str:
        rl = self.read_lock.__repr__()
        wl = self.write_lock.__repr__()
        return "<RWLock: {} {}>".format(rl, wl)

    def replace(self, new: T) -> None:
        self._wrapped = new
