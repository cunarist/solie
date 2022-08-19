from collections import OrderedDict
import threading

_object_locks = OrderedDict()


def hold(unique_name):
    global _object_locks
    if type(unique_name) is not str:
        return
    if unique_name in _object_locks.keys():
        object_lock = _object_locks[unique_name]
    else:
        object_lock = threading.Lock()
        _object_locks[unique_name] = object_lock
    if len(_object_locks) > 1024:
        _object_locks.popitem()
    return object_lock
