import os
from importlib import import_module, metadata
from inspect import getfile
from pathlib import Path

PACKAGE_VERSION = metadata.version("solie")
PACKAGE_PATH = Path(os.path.dirname(getfile(import_module("solie"))))
