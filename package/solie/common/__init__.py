from .connect_event import outsource
from .info import PACKAGE_PATH, PACKAGE_VERSION
from .parallel import PROCESS_COUNT, communicator, go, prepare_process_pool

__all__ = [
    "outsource",
    "go",
    "PROCESS_COUNT",
    "communicator",
    "prepare_process_pool",
    "PACKAGE_PATH",
    "PACKAGE_VERSION",
]
