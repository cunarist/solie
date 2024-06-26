import json
from pathlib import Path

import aiofiles
import aiofiles.os
import pandas as pd

from solie.common import go


async def examine_data_files(datapath: Path):
    # 5.0: Data settings
    try:
        filepath = datapath / "basics.json"
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            content = await file.read()
            data_settings = json.loads(content)
        await aiofiles.os.remove(filepath)
        filepath = datapath / "data_settings.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(data_settings, indent=2)
            await file.write(content)
    except Exception:
        pass

    # 5.0: Symbol column was added to auto order record
    try:
        filepath = datapath / "transactor" / "auto_order_record.pickle"
        auto_order_record: pd.DataFrame = await go(pd.read_pickle, filepath)
        if "Symbol" not in auto_order_record.columns:
            auto_order_record["Symbol"] = ""
            await go(auto_order_record.to_pickle, filepath)
    except Exception:
        pass

    # 5.0: Solie default strategy now has strategy code SLSLDS
    try:
        filepath = datapath / "transactor" / "automation_settings.json"
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            content = await file.read()
            automation_settings = json.loads(content)
        if automation_settings.get("strategy", None) == 2:
            automation_settings.pop("strategy")
            automation_settings["strategy_code"] = "SLSLDS"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(automation_settings, indent=2)
            await file.write(content)
    except Exception:
        pass

    # 6.0: Use strategy index instead of strategy code
    try:
        filepath = datapath / "transactor" / "automation_settings.json"
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            content = await file.read()
            automation_settings = json.loads(content)
        if "strategy_code" in automation_settings.keys():
            automation_settings.pop("strategy_code")
        if "strategy_index" not in automation_settings.keys():
            automation_settings["strategy_index"] = 0
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(automation_settings, indent=2)
            await file.write(content)
    except Exception:
        pass

    # 6.3: Possible causes are now `auto_trade` and `manual_trade`
    try:
        filepath = datapath / "transactor" / "asset_record.pickle"
        asset_record: pd.DataFrame = await go(pd.read_pickle, filepath)
        asset_record["Cause"] = asset_record["Cause"].replace("trade", "auto_trade")
        await go(asset_record.to_pickle, filepath)
    except Exception:
        pass

    # 8.5: Now strategist has `Strategies` object instead of `list[dict]`
    try:
        filepath = datapath / "strategist" / "strategies.json"
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            content = await file.read()
            strategies = json.loads(content)
        if not isinstance(strategies, list):
            raise ValueError("Already good")
        for strategy in strategies:
            strategy["risk_level"] = 2 - strategy["risk_level"]  # Reversed
        new_strategies = {"all": strategies}
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(new_strategies, indent=2)
            await file.write(content)
    except Exception:
        pass
