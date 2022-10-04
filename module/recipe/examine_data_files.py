import pickle
import copy
import os
import json
import shutil
import pandas as pd

from module.recipe import user_settings
from module.recipe import encrypted_pickle


def do():
    datapath = user_settings.get_app_settings()["datapath"]

    jobs = []

    # 1.1.2: changed type of realtime_data_chunks from list to deque
    def job():
        filepath = f"{datapath}/collector/realtime_data_chunks.pickle"
        with open(filepath, "rb") as file:
            realtime_data_chunks = copy.deepcopy(pickle.load(file))
        if isinstance(realtime_data_chunks, list):
            os.remove(filepath)

    jobs.append(job)

    # 2.0: renamed leverage_settings to mode_settings
    def job():
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

    jobs.append(job)

    # 2.11: included dependencies in the installer
    def job():
        if os.path.isdir("./habitat"):
            shutil.rmtree("./habitat")

    jobs.append(job)

    # 3.9: add ability to select token
    def job():
        filepath = f"{datapath}/data_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            data_settings = json.load(file)
        if "asset_token" not in data_settings.keys():
            data_settings["asset_token"] = "USDT"
        if "generated_timestamp" in data_settings.keys():
            data_settings.pop("generated_timestamp")
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(data_settings, file, indent=4)

    jobs.append(job)

    # 3.11: merge asset_trace and trade_record to asset_record
    def job():
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

    jobs.append(job)

    # 4.0: solsol default strategy now has code number 2
    def job():
        filepath = f"{datapath}/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if automation_settings.get("strategy", None) == 110:
            automation_settings["strategy"] = 2
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)

    jobs.append(job)

    # 5.0: data settings
    def job():
        filepath = f"{datapath}/basics.json"
        with open(filepath, "r", encoding="utf8") as file:
            data_settings = json.load(file)
        os.remove(filepath)
        filepath = f"{datapath}/data_settings.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(data_settings, file, indent=4)

    jobs.append(job)

    # 5.0: symbol column was added to auto order record
    def job():
        filepath = f"{datapath}/transactor/auto_order_record.pickle"
        auto_order_record = pd.read_pickle(filepath)
        if "Symbol" not in auto_order_record.columns:
            auto_order_record["Symbol"] = ""
            auto_order_record.to_pickle(filepath)

    jobs.append(job)

    # 5.0: solsol default strategy now has strategy code SLSLDS
    def job():
        filepath = f"{datapath}/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if automation_settings.get("strategy", None) == 2:
            automation_settings.pop("strategy")
            automation_settings["strategy_code"] = "SLSLDS"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)

    jobs.append(job)

    # 6.0: use strategy index instead of strategy code
    def job():
        filepath = f"{datapath}/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if "strategy_code" in automation_settings.keys():
            automation_settings.pop("strategy_code")
        if "strategy_index" not in automation_settings.keys():
            automation_settings["strategy_index"] = 0
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)

    jobs.append(job)

    # 6.1: discount code
    def job():
        filepath = f"{datapath}/transactor/fee_settings.slslsc"
        fee_settings = encrypted_pickle.read(filepath)
        if "discount" in fee_settings.keys():
            fee_settings.pop("discount")
        if "discount_code" not in fee_settings.keys():
            fee_settings["discount_code"] = ""
        encrypted_pickle.write(fee_settings, filepath)

    jobs.append(job)

    # 6.3: auto_trade and manual_trade
    def job():
        filepath = f"{datapath}/transactor/asset_record.pickle"
        asset_record = pd.read_pickle(filepath)
        asset_record["Cause"] = asset_record["Cause"].replace("trade", "auto_trade")
        asset_record.to_pickle(filepath)

    jobs.append(job)

    # 6.8: fee address column in auto order record
    def job():
        filepath = f"{datapath}/transactor/auto_order_record.pickle"
        auto_order_record = pd.read_pickle(filepath)
        is_something_done = False
        if "Net Profit" in auto_order_record.columns:
            auto_order_record = auto_order_record.drop(["Net Profit"], axis=1)
            is_something_done = True
        if "Fee Address" not in auto_order_record.columns:
            auto_order_record["Fee Address"] = ""
            is_something_done = True
        if is_something_done:
            auto_order_record.to_pickle(filepath)

    jobs.append(job)

    # run jobs
    for job in jobs:
        try:
            job()
        except Exception:
            pass


def do_first():
    # 5.0: app settings

    jobs = []

    def job():
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

    jobs.append(job)

    # 6.0: remove solsol license key

    def job():
        filepath = "./note/app_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            app_settings = json.load(file)
        if "license_key" in app_settings.keys():
            app_settings.pop("license_key")
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(app_settings, file, indent=4)

    jobs.append(job)

    # 6.0: terms of agreement

    def job():
        filepath = "./note/app_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            app_settings = json.load(file)
        if "is_agreement_read" not in app_settings.keys():
            app_settings["is_agreement_read"] = False
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(app_settings, file, indent=4)

    jobs.append(job)

    # run jobs
    for job in jobs:
        try:
            job()
        except Exception:
            pass
