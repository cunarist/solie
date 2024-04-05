from .connect_event import outsource
from .info import PACKAGE_NAME, PACKAGE_PATH, PACKAGE_VERSION
from .parallel import PROCESS_COUNT, go, prepare_process_pool, sync_manager

__all__ = [
    "outsource",
    "go",
    "PROCESS_COUNT",
    "sync_manager",
    "prepare_process_pool",
    "PACKAGE_PATH",
    "PACKAGE_VERSION",
    "PACKAGE_NAME",
]
