import copy
import json
import os

import aiofiles

import solie

_app_settings = {
    "datapath": None,
}
_data_settings = {
    "asset_token": None,
    "target_symbols": None,
}


async def load():
    global _app_settings
    global _data_settings

    filepath = f"{solie.PATH}/note/app_settings.json"
    if os.path.isfile(filepath):
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            content = await file.read()
            _app_settings = json.loads(content)

    datapath = _app_settings["datapath"]
    filepath = f"{datapath}/data_settings.json"
    if os.path.isfile(filepath):
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            content = await file.read()
            _data_settings = json.loads(content)


def get_app_settings() -> dict:
    return copy.deepcopy(_app_settings)


async def apply_app_settings(payload):
    global _app_settings
    payload = copy.deepcopy(payload)
    _app_settings = {**_app_settings, **payload}
    filepath = f"{solie.PATH}/note/app_settings.json"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    async with aiofiles.open(filepath, "w", encoding="utf8") as file:
        content = json.dumps(_app_settings, indent=4)
        await file.write(content)


def get_data_settings() -> dict:
    return copy.deepcopy(_data_settings)


async def apply_data_settings(payload):
    global _data_settings
    payload = copy.deepcopy(payload)
    _data_settings = {**_data_settings, **payload}
    datapath = _app_settings["datapath"]
    if datapath is not None:
        filepath = f"{datapath}/data_settings.json"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(_data_settings, indent=4)
            await file.write(content)
