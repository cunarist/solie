from pathlib import Path

import aiofiles
import aiofiles.os

from solie.common import PACKAGE_PATH

from .data_models import DataSettings

DATAPATH_FILE = PACKAGE_PATH / "datapath.txt"


async def read_datapath() -> Path | None:
    if await aiofiles.os.path.isfile(DATAPATH_FILE):
        async with aiofiles.open(DATAPATH_FILE, "r", encoding="utf8") as file:
            datapath = Path(await file.read())
        if await aiofiles.os.path.isdir(datapath):
            return datapath
        else:
            return None
    else:
        return None


async def save_datapath(datapath: Path | None):
    if datapath:
        async with aiofiles.open(DATAPATH_FILE, "w", encoding="utf8") as file:
            await file.write(str(datapath))
    else:
        await aiofiles.os.remove(DATAPATH_FILE)


async def read_data_settings(datapath: Path) -> DataSettings | None:
    filepath = datapath / "data_settings.json"
    if await aiofiles.os.path.isfile(filepath):
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            data_settings = DataSettings.model_validate_json(await file.read())
        return data_settings
    else:
        return None


async def save_data_settings(data_settings: DataSettings, datapath: Path):
    filepath = datapath / "data_settings.json"
    async with aiofiles.open(filepath, "w", encoding="utf8") as file:
        await file.write(data_settings.model_dump_json(indent=2))
