from dataclasses import dataclass
from pathlib import Path

import aiofiles
from dataclasses_json import DataClassJsonMixin

import solie

APP_SETTINGS_PATH = solie.info.PATH / "note" / "app_settings.json"


@dataclass
class AppSettings(DataClassJsonMixin):
    datapath: str


async def read_app_settings() -> AppSettings | None:
    if APP_SETTINGS_PATH.is_file():
        async with aiofiles.open(APP_SETTINGS_PATH, "r", encoding="utf8") as file:
            app_settings = AppSettings.from_json(await file.read())
        return app_settings
    else:
        return None


async def save_app_settings(app_settings: AppSettings):
    async with aiofiles.open(APP_SETTINGS_PATH, "w", encoding="utf8") as file:
        await file.write(app_settings.to_json(indent=2))


@dataclass
class DataSettings(DataClassJsonMixin):
    asset_token: str
    target_symbols: list[str]


async def read_data_settings(datapath: Path) -> DataSettings | None:
    filepath = datapath / "data_settings.json"
    if filepath.is_file():
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            data_settings = DataSettings.from_json(await file.read())
        return data_settings
    else:
        return None


async def save_data_settings(data_settings: DataSettings, datapath: Path):
    filepath = datapath / "data_settings.json"
    async with aiofiles.open(filepath, "w", encoding="utf8") as file:
        await file.write(data_settings.to_json(indent=2))
