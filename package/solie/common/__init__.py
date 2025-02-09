from .concurrency import spawn
from .connect_event import outsource
from .info import PACKAGE_NAME, PACKAGE_PATH, PACKAGE_VERSION
from .parallelism import PROCESS_COUNT, get_sync_manager, go, prepare_process_pool

__all__ = [
    "PACKAGE_NAME",
    "PACKAGE_PATH",
    "PACKAGE_VERSION",
    "PROCESS_COUNT",
    "get_sync_manager",
    "go",
    "outsource",
    "prepare_process_pool",
    "spawn",
]
