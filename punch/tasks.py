from dataclasses import dataclass
import datetime

@dataclass
class TaskEntry:
    finish: datetime.datetime
    category: str
    task: str
    notes: str
    duration: datetime.timedelta

SEPARATOR = '|'

def read_tasklog(taskfile):
    """
    Reads the task log from a file and returns a list of TaskEntry objects.
    """
    tasklog = []
    try:
        with open('tasks.txt', 'r') as f:
            for line in f:
                tasklog.append(parse_task(line, tasklog))
    except FileNotFoundError:
        pass
    return tasklog

def parse_task(line, tasklog):
    parts = line.strip().split(SEPARATOR)
    parts = [s.strip() for s in parts]
    # Allow notes to be optional
    if len(parts) == 3:
        finish_str, category, task = parts
        notes = ""
    elif len(parts) >= 4:
        finish_str, category, task, notes = parts[:4]
    else:
        raise ValueError("Invalid task entry format")
    finish = datetime.datetime.strptime(finish_str.strip(), '%Y-%m-%d %H:%M')
    if len(tasklog) > 0 and finish < tasklog[-1].finish:
        raise ValueError("Entries must be in chronological order")

    duration = finish - tasklog[-1].finish if len(tasklog) > 0 else datetime.timedelta(0)
    return TaskEntry(finish, category, task, notes, duration)

def get_recent_tasks(taskfile, category):
    """
    Returns a list of recent tasks for a given category, with duplicates removed (most recent first).
    """
    tasklog = read_tasklog(taskfile)
    seen = set()
    recent_tasks = []
    for entry in reversed(tasklog):
        if entry.category == category and entry.task not in seen:
            recent_tasks.append(entry)
            seen.add(entry.task)
    return recent_tasks

def write_task(taskfile, category, task, notes):
    """
    Writes a new task entry to the task log.
    """
    finish = datetime.datetime.now()

    # Compose the entry parts, omitting notes and separator if notes is empty
    entry_parts = [
        finish.strftime('%Y-%m-%d %H:%M'),
        category,
        task
    ]
    line = f" {SEPARATOR} ".join(entry_parts)
    if notes and notes.strip():
        line += f" {SEPARATOR} {notes.strip()}"
    line += "\n"

    with open(taskfile, 'a') as f:
        f.write(line)