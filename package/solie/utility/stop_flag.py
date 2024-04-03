last_task_id = 0
flags = {}


def make_stop_flag(task_name: str) -> int:
    global last_task_id
    new_task_id = last_task_id + 1
    flags[task_name] = new_task_id
    last_task_id = new_task_id
    return new_task_id


def find_stop_flag(task_name: str, current_task_id: int) -> bool:
    if task_name in flags.keys():
        if flags[task_name] > current_task_id:
            return True
        else:
            return False
    else:
        return False
