import pickle
import copy
import os
import json
import shutil
from datetime import datetime, timezone


def do(datapath):
    # 1.1.2: changed type of realtime_data_chunks from list to deque
    try:
        filepath = datapath + "/collector/realtime_data_chunks.pickle"
        with open(filepath, "rb") as file:
            realtime_data_chunks = copy.deepcopy(pickle.load(file))
        if isinstance(realtime_data_chunks, list):
            os.remove(filepath)
    except FileNotFoundError:
        pass

    # 2.0: renamed leverage_settings to mode_settings
    try:
        filepath = datapath + "/transactor/leverage_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            desired_leverage = json.load(file)["desired_leverage"]
        os.remove(filepath)
        mode_settings = {
            "desired_leverage": desired_leverage,
        }
        filepath = datapath + "/transactor/mode_settings.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(mode_settings, file, indent=4)
    except FileNotFoundError:
        pass

    # 2.11: included dependencies in the installer
    if os.path.isdir("./habitat"):
        shutil.rmtree("./habitat", ignore_errors=True)

    # 3.9: add ability to select token
    try:
        filepath = datapath + "/basics.json"
        with open(filepath, "r", encoding="utf8") as file:
            basics = json.load(file)
        if "asset_token" not in basics.keys():
            basics["asset_token"] = "USDT"
        if "modified_timestamp" not in basics.keys():
            basics["modified_timestamp"] = int(datetime.now(timezone.utc).timestamp())
        if "generated_timestamp" in basics.keys():
            basics.pop("generated_timestamp")
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(basics, file, indent=4)
    except FileNotFoundError:
        pass

    # 3.11: merge asset_trace and trade_record to asset_record
    try:
        filepath = datapath + "/transactor/asset_trace.pickle"
        with open(filepath, "rb") as file:
            asset_trace = pickle.load(file)
        filepath = datapath + "/transactor/trade_record.pickle"
        with open(filepath, "rb") as file:
            trade_record = pickle.load(file)

        asset_record = trade_record.copy()
        asset_record["Cause"] = "other"
        asset_record["Result Asset"] = asset_trace

        filepath = datapath + "/transactor/asset_record.pickle"
        with open(filepath, "wb") as file:
            pickle.dump(asset_record, file)
        filepath = datapath + "/transactor/asset_trace.pickle"
        os.remove(filepath)
        filepath = datapath + "/transactor/trade_record.pickle"
        os.remove(filepath)

    except FileNotFoundError:
        pass

    # 4.0: solsol default strategy now has code number 2
    try:
        filepath = datapath + "/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if automation_settings["strategy"] == 110:
            automation_settings["strategy"] = 2
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)
    except FileNotFoundError:
        pass
