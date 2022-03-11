import pickle
import copy
import os
import json


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
