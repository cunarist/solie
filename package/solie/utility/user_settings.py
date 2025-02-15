from pathlib import Path
from types import CodeType

import aiofiles
import aiofiles.os
from pydantic import BaseModel

from solie.common import PACKAGE_PATH

from .data_models import (
    DataSettings,
    DecisionInput,
    IndicatorInput,
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


class SavedStrategy(Strategy):
    indicator_script: str = "pass"
    decision_script: str = "pass"

    def create_indicators(self, given: IndicatorInput):
        target_symbols = given.target_symbols
        candle_data = given.candle_data
        new_indicators = given.new_indicators

        code_field = "_compiled_indicator_script"
        try:
            code: CodeType = getattr(self, code_field)
        except AttributeError:
            code = compile(self.indicator_script, "<string>", "exec")
            setattr(self, code_field, code)

        namespace = {
            "target_symbols": target_symbols,
            "candle_data": candle_data,
            "new_indicators": new_indicators,
        }
        exec(code, namespace)

    def create_decisions(self, given: DecisionInput):
        target_symbols = given.target_symbols
        account_state = given.account_state
        current_moment = given.current_moment
        current_candle_data = given.current_candle_data
        current_indicators = given.current_indicators
        scribbles = given.scribbles
        new_decisions = given.new_decisions

        code_field = "_compiled_decision_script"
        try:
            code: CodeType = getattr(self, code_field)
        except AttributeError:
            code = compile(self.decision_script, "<string>", "exec")
            setattr(self, code_field, code)

        namespace = {
            "target_symbols": target_symbols,
            "current_moment": current_moment,
            "current_candle_data": current_candle_data,
            "current_indicators": current_indicators,
            "account_state": account_state,
            "scribbles": scribbles,
            "decisions": new_decisions,
        }
        exec(code, namespace)


class SavedStrategies(BaseModel):
    all: list[SavedStrategy]


class SolieConfig:
    def __init__(self):
        self.strategies: list[Strategy] = []

    def add_strategy(self, strategy: Strategy):
        self.strategies.append(strategy)
