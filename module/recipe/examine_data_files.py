import pickle
import copy
import os
import json
import shutil
import pandas as pd

from module.recipe import user_settings


def do():
    datapath = user_settings.get_app_settings()["datapath"]

    # 1.1.2: changed type of realtime_data_chunks from list to deque
    try:
        filepath = f"{datapath}/collector/realtime_data_chunks.pickle"
        with open(filepath, "rb") as file:
            realtime_data_chunks = copy.deepcopy(pickle.load(file))
        if isinstance(realtime_data_chunks, list):
            os.remove(filepath)
    except Exception:
        pass

    # 2.0: renamed leverage_settings to mode_settings
    try:
        filepath = f"{datapath}/transactor/leverage_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            desired_leverage = json.load(file)["desired_leverage"]
        os.remove(filepath)
        mode_settings = {
            "desired_leverage": desired_leverage,
        }
        filepath = f"{datapath}/transactor/mode_settings.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(mode_settings, file, indent=4)
    except Exception:
        pass

    # 2.11: included dependencies in the installer
    if os.path.isdir("./habitat"):
        shutil.rmtree("./habitat", ignore_errors=True)

    # 3.9: add ability to select token
    try:
        filepath = f"{datapath}/data_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            data_settings = json.load(file)
        if "asset_token" not in data_settings.keys():
            data_settings["asset_token"] = "USDT"
        if "generated_timestamp" in data_settings.keys():
            data_settings.pop("generated_timestamp")
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(data_settings, file, indent=4)
    except Exception:
        pass

    # 3.11: merge asset_trace and trade_record to asset_record
    try:
        filepath = f"{datapath}/transactor/asset_trace.pickle"
        with open(filepath, "rb") as file:
            asset_trace = pickle.load(file)
        filepath = f"{datapath}/transactor/trade_record.pickle"
        with open(filepath, "rb") as file:
            trade_record = pickle.load(file)

        asset_record = trade_record.copy()
        asset_record["Cause"] = "other"
        asset_record["Result Asset"] = asset_trace

        filepath = f"{datapath}/transactor/asset_record.pickle"
        with open(filepath, "wb") as file:
            pickle.dump(asset_record, file)
        filepath = f"{datapath}/transactor/asset_trace.pickle"
        os.remove(filepath)
        filepath = f"{datapath}/transactor/trade_record.pickle"
        os.remove(filepath)

    except Exception:
        pass

    # 4.0: solsol default strategy now has code number 2
    try:
        filepath = f"{datapath}/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if automation_settings.get("strategy", None) == 110:
            automation_settings["strategy"] = 2
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)
    except Exception:
        pass

    # 5.0: data settings
    try:
        filepath = f"{datapath}/basics.json"
        with open(filepath, "r", encoding="utf8") as file:
            data_settings = json.load(file)
        os.remove(filepath)
        filepath = f"{datapath}/data_settings.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(data_settings, file, indent=4)
    except Exception:
        pass

    # 5.0: symbol column was added to auto order record
    try:
        filepath = f"{datapath}/transactor/auto_order_record.pickle"
        auto_order_record = pd.read_pickle(filepath)
        if "Symbol" not in auto_order_record.columns:
            auto_order_record["Symbol"] = ""
            auto_order_record.to_pickle(filepath)
    except Exception:
        pass

    # 5.0: solsol default strategy now has strategy code SLSLDS
    try:
        filepath = f"{datapath}/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if automation_settings.get("strategy", None) == 2:
            automation_settings.pop("strategy")
            automation_settings["strategy_code"] = "SLSLDS"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)
    except Exception:
        pass

    # 6.0: use strategy index instead of strategy code
    try:
        filepath = f"{datapath}/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if "strategy_code" in automation_settings.keys():
            automation_settings.pop("strategy_code")
        if "strategy_index" not in automation_settings.keys():
            automation_settings["strategy_index"] = 0
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)
    except Exception:
        pass


def do_first():
    # 5.0: app settings

    try:
        filepath = "./note/datapath.txt"
        with open(filepath, "r", encoding="utf8") as file:
            datapath = file.read()
        os.remove(filepath)
        filepath = "./note/license_key.txt"
        with open(filepath, "r", encoding="utf8") as file:
            license_key = file.read()
        os.remove(filepath)
        app_settings = {
            "license_key": license_key,
            "datapath": datapath,
        }
        filepath = "./note/app_settings.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(app_settings, file, indent=4)
    except Exception:
        pass

    # 6.0: remove solsol license key

    try:
        filepath = "./note/app_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            app_settings = json.load(file)
        if "license_key" in app_settings.keys():
            app_settings.pop("license_key")
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(app_settings, file, indent=4)
    except Exception:
        pass
