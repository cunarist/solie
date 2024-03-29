import json
import os
from pathlib import Path

import aiofiles
import pandas as pd

from solie.parallel import go
from solie.utility import user_settings


async def do():
    datapath_str = user_settings.get_app_settings()["datapath"]
    if datapath_str is None:
        return
    datapath = Path(datapath_str)

    # 5.0: data settings
    try:
        filepath = datapath / "basics.json"
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            content = await file.read()
            data_settings = json.loads(content)
        os.remove(filepath)
        filepath = datapath / "data_settings.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(data_settings, indent=4)
            await file.write(content)
    except Exception:
        pass

    # 5.0: symbol column was added to auto order record
    try:
        filepath = datapath / "transactor" / "auto_order_record.pickle"
        auto_order_record: pd.DataFrame = await go(pd.read_pickle, filepath)
        if "Symbol" not in auto_order_record.columns:
            auto_order_record["Symbol"] = ""
            await go(auto_order_record.to_pickle, filepath)
    except Exception:
        pass

    # 5.0: solie default strategy now has strategy code SLSLDS
    try:
        filepath = datapath / "transactor" / "automation_settings.json"
        async with aiofiles.open(filepath, "r", encoding="utf8") as file:
            content = await file.read()
            automation_settings = json.loads(content)
        if automation_settings.get("strategy", None) == 2:
            automation_settings.pop("strategy")
            automation_settings["strategy_code"] = "SLSLDS"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(automation_settings, indent=4)
            await file.write(content)
    except Exception:
        pass

    # 6.0: use strategy index instead of strategy code
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
            content = json.dumps(automation_settings, indent=4)
            await file.write(content)
    except Exception:
        pass

    # 6.3: auto_trade and manual_trade
    try:
        filepath = datapath / "transactor" / "asset_record.pickle"
        asset_record: pd.DataFrame = await go(pd.read_pickle, filepath)
        asset_record["Cause"] = asset_record["Cause"].replace("trade", "auto_trade")
        await go(asset_record.to_pickle, filepath)
    except Exception:
        pass
