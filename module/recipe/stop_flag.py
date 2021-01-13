_LAST_TASK_ID = 0
_FLAGS = {}


def make(task_name):
    global _LAST_TASK_ID
    new_task_id = _LAST_TASK_ID + 1
    _FLAGS[task_name] = new_task_id
    _LAST_TASK_ID = new_task_id
    return new_task_id


def find(task_name, current_task_id):
    if task_name in _FLAGS.keys():
        if _FLAGS[task_name] > current_task_id:
            return True
        else:
            return False
    else:
        return False
