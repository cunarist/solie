_last_task_id = 0
_flags = {}


def make(task_name):
    global _last_task_id
    new_task_id = _last_task_id + 1
    _flags[task_name] = new_task_id
    _last_task_id = new_task_id
    return new_task_id


def find(task_name, current_task_id):
    if task_name in _flags.keys():
        if _flags[task_name] > current_task_id:
            return True
        else:
            return False
    else:
        return False
