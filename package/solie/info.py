import os
from importlib import import_module, metadata
from inspect import getfile
from pathlib import Path

VERSION = metadata.version("solie")
PATH = Path(os.path.dirname(getfile(import_module("solie"))))
