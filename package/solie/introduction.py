import inspect
import os
from importlib import metadata

import solie

VERSION = metadata.version("solie")
PATH = os.path.dirname(inspect.getfile(solie)).replace("\\", "/")
