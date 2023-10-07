from task import Task

def get_task_under_construction(chat_id):
    global task_under_construction

    if chat_id in task_under_construction:
        return task_under_construction[chat_id]

    task_under_construction[chat_id] = Task()
    return task_under_construction[chat_id]

def set_task_under_construction(chat_id, value):
    global task_under_construction

    task_under_construction[chat_id] = value

def get_task_under_construction_swap_buffer(chat_id):
    global task_under_construction_swap_buffer

    if chat_id in task_under_construction_swap_buffer:
        return task_under_construction_swap_buffer[chat_id]

    task_under_construction[chat_id] = Task()
    return task_under_construction_swap_buffer[chat_id]

def set_task_under_construction_buffer(chat_id, value):
    global task_under_construction_swap_buffer

    task_under_construction_swap_buffer[chat_id] = value