from dataclasses import dataclass
from pathlib import Path

import aiofiles
import aiofiles.os
from dataclasses_json import DataClassJsonMixin

import solie

DATAPATH_FILE = solie.info.PATH / "datapath.txt"


async def read_datapath() -> str | None:
    if await aiofiles.os.path.isfile(DATAPATH_FILE):
        async with aiofiles.open(DATAPATH_FILE, "r", encoding="utf8") as file:
            datapath = await file.read()
        if await aiofiles.os.path.isdir(datapath):
            return datapath
        else:
            return None
    else:
        return None


async def save_datapth(datapath: str | None):
    if datapath:
        async with aiofiles.open(DATAPATH_FILE, "w", encoding="utf8") as file:
            await file.write(datapath)
    else:
        await aiofiles.os.remove(DATAPATH_FILE)


@dataclass
class DataSettings(DataClassJsonMixin):
    asset_token: str
    target_symbols: list[str]


async def read_data_settings(datapath: Path) -> DataSettings | None:
    filepath = datapath / "data_settings.json"
    if await aiofiles.os.path.isfile(filepath):
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            data_settings = DataSettings.from_json(await file.read())
        return data_settings
    else:
        return None


async def save_data_settings(data_settings: DataSettings, datapath: Path):
    filepath = datapath / "data_settings.json"
    async with aiofiles.open(filepath, "w", encoding="utf8") as file:
        await file.write(data_settings.to_json(indent=2))
