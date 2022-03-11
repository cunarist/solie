import pickle
import copy
import os


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
