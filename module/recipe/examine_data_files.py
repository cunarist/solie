import os
import json
import pandas as pd

from module.recipe import user_settings


def do():
    datapath = user_settings.get_app_settings()["datapath"]

    jobs = []

    # 5.0: data settings
    def job_ds():
        filepath = f"{datapath}/basics.json"
        with open(filepath, "r", encoding="utf8") as file:
            data_settings = json.load(file)
        os.remove(filepath)
        filepath = f"{datapath}/data_settings.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(data_settings, file, indent=4)

    jobs.append(job_ds)

    # 5.0: symbol column was added to auto order record
    def job_sc():
        filepath = f"{datapath}/transactor/auto_order_record.pickle"
        auto_order_record = pd.read_pickle(filepath)
        if "Symbol" not in auto_order_record.columns:
            auto_order_record["Symbol"] = ""
            auto_order_record.to_pickle(filepath)

    jobs.append(job_sc)

    # 5.0: solie default strategy now has strategy code SLSLDS
    def job_ns():
        filepath = f"{datapath}/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if automation_settings.get("strategy", None) == 2:
            automation_settings.pop("strategy")
            automation_settings["strategy_code"] = "SLSLDS"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)

    jobs.append(job_ns)

    # 6.0: use strategy index instead of strategy code
    def job_si():
        filepath = f"{datapath}/transactor/automation_settings.json"
        with open(filepath, "r", encoding="utf8") as file:
            automation_settings = json.load(file)
        if "strategy_code" in automation_settings.keys():
            automation_settings.pop("strategy_code")
        if "strategy_index" not in automation_settings.keys():
            automation_settings["strategy_index"] = 0
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(automation_settings, file, indent=4)

    jobs.append(job_si)

    # 6.3: auto_trade and manual_trade
    def job_at():
        filepath = f"{datapath}/transactor/asset_record.pickle"
        asset_record = pd.read_pickle(filepath)
        asset_record["Cause"] = asset_record["Cause"].replace("trade", "auto_trade")
        asset_record.to_pickle(filepath)

    jobs.append(job_at)

    # run jobs
    for job in jobs:
        try:
            job()
        except Exception:
            pass
