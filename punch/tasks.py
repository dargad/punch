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
    The first task of each day will have a duration of 0, subsequent tasks will have duration relative to the previous task of that day.
    """
    tasklog = []
    prev_entry_by_day = {}
    try:
        with open(taskfile, 'r') as f:
            for line in f:
                entry = parse_task(line)
                day = entry.finish.date()
                if day in prev_entry_by_day:
                    prev_entry = prev_entry_by_day[day]
                    duration = entry.finish - prev_entry.finish
                else:
                    duration = datetime.timedelta(0)
                # Create a new TaskEntry with the correct duration
                entry = TaskEntry(entry.finish, entry.category, entry.task, entry.notes, duration)
                tasklog.append(entry)
                prev_entry_by_day[day] = entry
    except FileNotFoundError:
        pass
    return tasklog

def parse_task(line):
    parts = line.strip().split(SEPARATOR)
    parts = [s.strip() for s in parts]
    # Handle different possible formats
    if len(parts) == 2:
        finish_str, task = parts
        category = ""
        notes = ""
    elif len(parts) == 3:
        finish_str, category, task = parts
        notes = ""
    elif len(parts) >= 4:
        finish_str, category, task, notes = parts[:4]
    else:
        raise ValueError("Invalid task entry format")
    finish = datetime.datetime.strptime(finish_str.strip(), '%Y-%m-%d %H:%M')
    return TaskEntry(finish, category, task, notes, duration=datetime.timedelta(0))

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
    If category is empty, omit it from the output.
    """
    finish = datetime.datetime.now()

    entry_parts = [finish.strftime('%Y-%m-%d %H:%M')]
    if category:
        entry_parts.append(category)
    entry_parts.append(task)

    line = f" {SEPARATOR} ".join(entry_parts)
    if notes and notes.strip():
        line += f" {SEPARATOR} {notes.strip()}"
    line += "\n"

    with open(taskfile, 'a') as f:
        f.write(line)

def parse_new_task_string(task_string, categories):
    """
    Parses a new task string and returns a TaskEntry.
    Accepts:
      - Any string ending with * or ** (no category, just task and optional notes, keep * or ** in the task)
      - A string in format <short-category> : <task-name> [: <task-notes>]
    Uses the current time as the finish timestamp.
    Converts short category symbol to full category name using the categories dict.
    Raises ValueError if the category symbol is not recognized.
    """
    finish = datetime.datetime.now()
    duration = datetime.timedelta(0)

    stripped = task_string.strip()
    # If the string ends with * or **, treat as category-less task (keep * or ** in the task)
    if stripped.endswith("*"):
        # Split notes if present (by " : ")
        if " : " in stripped:
            task, notes = stripped.rsplit(" : ", 1)
        else:
            task, notes = stripped, ""
        return TaskEntry(finish, "", task, notes, duration)

    # Otherwise, expect <short-category> : <task-name> [: <task-notes>]
    parts = [part.strip() for part in task_string.split(":", 2)]
    if len(parts) < 2:
        raise ValueError("Task string must be in the format '<short-category> : <task-name> [: <task-notes>]' or end with '*' for category-less tasks")
    input_category = parts[0]
    task = parts[1]
    notes = parts[2] if len(parts) == 3 else ""

    # Build a mapping from short symbol to full category name
    short_to_full = {v['short']: k for k, v in categories.items() if 'short' in v}

    # Replace short symbol with full category name if possible, else raise error
    if input_category in short_to_full:
        category = short_to_full[input_category]
    elif input_category in categories:
        category = input_category
    else:
        raise ValueError(f"Unknown category symbol or name: '{input_category}'")

    return TaskEntry(finish, category, task, notes, duration)