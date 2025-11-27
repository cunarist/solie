"""Common utilities and shared functionality."""

from .concurrency import UniqueTask, spawn
from .connect_event import outsource
from .info import PACKAGE_NAME, PACKAGE_PATH, PACKAGE_VERSION
from .parallelism import (
    PROCESS_COUNT,
    get_sync_manager,
    prepare_process_pool,
    spawn_blocking,
)

__all__ = [
    "PACKAGE_NAME",
    "PACKAGE_PATH",
    "PACKAGE_VERSION",
    "PROCESS_COUNT",
    "UniqueTask",
    "get_sync_manager",
    "outsource",
    "prepare_process_pool",
    "spawn",
    "spawn_blocking",
]
