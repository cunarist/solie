from collections import OrderedDict
import threading

_object_locks = OrderedDict()


def hold(anything):
    global _object_locks
    object_id = id(anything)
    if object_id in _object_locks.keys():
        object_lock = _object_locks[object_id]
    else:
        object_lock = threading.Lock()
        _object_locks[object_id] = object_lock
    if len(_object_locks) > 1024:
        _object_locks.popitem()
    return object_lock
