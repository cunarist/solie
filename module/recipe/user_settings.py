import os
import copy
import json
from datetime import datetime, timezone

_license_key = None
_datapath = None
_basics = {}


def load():
    global _license_key
    global _datapath
    global _basics

    if os.path.isfile("./note/license_key.txt"):
        with open("./note/license_key.txt", "r", encoding="utf8") as file:
            _license_key = file.read()

    if os.path.isfile("./note/datapath.txt"):
        with open("./note/datapath.txt", "r", encoding="utf8") as file:
            datapath = file.read()
            if os.path.isdir(datapath):
                _datapath = datapath

    if _datapath is not None:
        if os.path.isfile(f"{_datapath}/basics.json"):
            with open(f"{_datapath}/basics.json", "r", encoding="utf8") as file:
                _basics = json.load(file)


load()


def get_license_key():
    return _license_key


def set_license_key(license_key):
    global _license_key
    _license_key = license_key
    os.makedirs(os.path.dirname("./note/license_key.txt"), exist_ok=True)
    with open("./note/license_key.txt", "w", encoding="utf8") as file:
        file.write(license_key)


def get_datapath():
    return _datapath


def set_datapath(datapath):
    global _datapath
    _datapath = datapath
    os.makedirs(os.path.dirname("./note/datapath.txt"), exist_ok=True)
    with open("./note/datapath.txt", "w", encoding="utf8") as file:
        file.write(datapath)


def get_basics():
    return copy.deepcopy(_basics)


def apply_basics(basics):
    global _basics
    basics = copy.deepcopy(basics)
    basics = {**basics, **_basics}
    basics["modified_timestamp"] = int(datetime.now(timezone.utc).timestamp())
    _basics = basics
    os.makedirs(os.path.dirname(f"{_datapath}/basics.json"), exist_ok=True)
    with open(f"{_datapath}/basics.json", "w", encoding="utf8") as file:
        json.dump(basics, file, indent=4)
