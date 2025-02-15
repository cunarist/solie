from abc import abstractmethod
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os
import pandas as pd

from solie.common import PACKAGE_PATH

from .data_models import (
    AccountState,
    DataSettings,
    Decision,
    OrderType,
    Strategy,
)

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


class FixedStrategy(Strategy):
    @abstractmethod
    def create_indicators(
        self,
        target_symbols: list[str],
        candle_data: pd.DataFrame,
        new_indicators: dict[str, pd.Series],
    ):
        pass

    @abstractmethod
    def create_decisions(
        self,
        target_symbols: list[str],
        account_state: AccountState,
        current_candle_data: dict[str, float],
        current_indicators: dict[str, float],
        scribbles: dict[Any, Any],
        new_decisions: dict[str, dict[OrderType, Decision]],
    ):
        pass


class SolieConfig:
    def __init__(self):
        self.fixed_strategies: list[FixedStrategy] = []

    def add_strategy(self, strategy: FixedStrategy):
        self.fixed_strategies.append(strategy)
