import os
from importlib import import_module, metadata
from inspect import getfile
from pathlib import Path

PACKAGE_NAME = __name__.split(".")[0]
PACKAGE_VERSION = metadata.version(PACKAGE_NAME)
PACKAGE_PATH = Path(os.path.dirname(getfile(import_module(PACKAGE_NAME))))
