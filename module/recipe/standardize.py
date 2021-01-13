import os
import copy
import json

_LICENSE_KEY = None
_DATAPATH = None
_BASICS = None


def load():
    global _LICENSE_KEY
    global _DATAPATH
    global _BASICS

    if os.path.isfile("./note/license_key.txt"):
        with open("./note/license_key.txt", "r", encoding="utf8") as file:
            _LICENSE_KEY = file.read()

    if os.path.isfile("./note/datapath.txt"):
        with open("./note/datapath.txt", "r", encoding="utf8") as file:
            datapath = file.read()
            if os.path.isdir(datapath):
                _DATAPATH = datapath

    if _DATAPATH is not None:
        if os.path.isfile(f"{_DATAPATH}/basics.json"):
            with open(f"{_DATAPATH}/basics.json", "r", encoding="utf8") as file:
                _BASICS = json.load(file)


load()


def get_license_key():
    return _LICENSE_KEY


def set_license_key(license_key):
    global _LICENSE_KEY
    _LICENSE_KEY = license_key
    os.makedirs(os.path.dirname("./note/license_key.txt"), exist_ok=True)
    with open("./note/license_key.txt", "w", encoding="utf8") as file:
        file.write(license_key)


def get_datapath():
    return _DATAPATH


def set_datapath(datapath):
    global _DATAPATH
    _DATAPATH = datapath
    os.makedirs(os.path.dirname("./note/datapath.txt"), exist_ok=True)
    with open("./note/datapath.txt", "w", encoding="utf8") as file:
        file.write(datapath)


def get_basics():
    return copy.deepcopy(_BASICS)


def set_basics(basics):
    global _BASICS
    basics = copy.deepcopy(basics)
    _BASICS = basics
    os.makedirs(os.path.dirname(f"{_DATAPATH}/basics.json"), exist_ok=True)
    with open(f"{_DATAPATH}/basics.json", "w", encoding="utf8") as file:
        json.dump(basics, file, indent=4)
