import threading

object_locks = {}


def hold(unique_name):
    global object_locks
    if type(unique_name) is not str:
        return
    if unique_name in object_locks.keys():
        object_lock = object_locks[unique_name]
    else:
        object_lock = threading.Lock()
        object_locks[unique_name] = object_lock
    if len(object_locks) > 1024:
        object_locks.popitem()
    return object_lock
