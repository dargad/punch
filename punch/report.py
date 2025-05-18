from rich.tree import Tree
from rich.console import Console
import datetime
from punch.tasks import read_tasklog

def generate_report(tasks_file, date_from, date_to, collapse=True):
    """
    Generate a report of all tasks grouped by category between date_from and date_to (inclusive).
    date_to means all tasks finished before the end of that day.
    Assumes date_from and date_to are datetime.date objects.
    If collapse is True, sum duration of all tasks with the same name (notes are ignored).
    Returns a dict: {category: [ (task, notes, duration) or (task, duration) ]}
    """
    # Convert date_from and date_to to datetime for comparison
    date_from_dt = datetime.datetime.combine(date_from, datetime.time.min)
    date_to_dt = datetime.datetime.combine(date_to, datetime.time.max)

    tasklog = read_tasklog(tasks_file)
    # Filter tasks in the date range and skip tasks with duration 0 or ending with **
    filtered = [
        entry for entry in tasklog
        if date_from_dt <= entry.finish <= date_to_dt
        and entry.duration.total_seconds() > 0
        and not entry.task.endswith("**")
    ]

    # Group by category
    categories = {}
    for entry in filtered:
        cat = entry.category or "(no category)"
        categories.setdefault(cat, []).append(entry)

    report = {}
    for cat, entries in sorted(categories.items()):
        if collapse:
            # Collapse: sum durations for each unique task name (notes ignored)
            task_durations = {}
            for entry in entries:
                if entry.task not in task_durations:
                    task_durations[entry.task] = datetime.timedelta(0)
                task_durations[entry.task] += entry.duration
            report[cat] = [(task, total_duration) for task, total_duration in sorted(task_durations.items())]
        else:
            report[cat] = []
            for entry in entries:
                report[cat].append((entry.task, entry.notes, entry.duration))
    return report