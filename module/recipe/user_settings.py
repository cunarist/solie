import os
import copy
import json

_app_settings = {
    "datapath": None,
}
_data_settings = {
    "asset_token": None,
    "target_symbols": None,
}


def load():
    global _app_settings
    global _data_settings

    if os.path.isfile("./note/app_settings.json"):
        with open("./note/app_settings.json", "r", encoding="utf8") as file:
            _app_settings = json.load(file)

    datapath = _app_settings["datapath"]
    if os.path.isfile(f"{datapath}/data_settings.json"):
        with open(f"{datapath}/data_settings.json", "r", encoding="utf8") as file:
            _data_settings = json.load(file)


def get_app_settings():
    return copy.deepcopy(_app_settings)


def apply_app_settings(payload):
    global _app_settings
    payload = copy.deepcopy(payload)
    _app_settings = {**_app_settings, **payload}
    os.makedirs(os.path.dirname("./note/app_settings.json"), exist_ok=True)
    with open("./note/app_settings.json", "w", encoding="utf8") as file:
        json.dump(_app_settings, file, indent=4)


def get_data_settings():
    return copy.deepcopy(_data_settings)


def apply_data_settings(payload):
    global _data_settings
    payload = copy.deepcopy(payload)
    _data_settings = {**_data_settings, **payload}
    datapath = _app_settings["datapath"]
    if datapath is not None:
        os.makedirs(os.path.dirname(f"{datapath}/data_settings.json"), exist_ok=True)
        with open(f"{datapath}/data_settings.json", "w", encoding="utf8") as file:
            json.dump(_data_settings, file, indent=4)
