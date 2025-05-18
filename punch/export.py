import csv
import io
import datetime
from punch.tasks import read_tasklog

def export_json(tasks_file, date_from, date_to):
    """
    Export all tasks as a list of dicts (one per entry) between date_from and date_to (inclusive).
    Skips tasks with duration 0 or ending with '**'.
    Each dict contains: category, task, notes, finish (ISO), duration_minutes (int).
    """
    date_from_dt = datetime.datetime.combine(date_from, datetime.time.min)
    date_to_dt = datetime.datetime.combine(date_to, datetime.time.max)

    tasklog = read_tasklog(tasks_file)
    exported = []
    for entry in tasklog:
        if not (date_from_dt <= entry.finish <= date_to_dt):
            continue
        if entry.duration.total_seconds() == 0:
            continue
        if entry.task.endswith("**"):
            continue
        exported.append({
            "category": entry.category,
            "task": entry.task,
            "notes": entry.notes,
            "finish": entry.finish.isoformat(),
            "duration_minutes": int(entry.duration.total_seconds() // 60),
        })
    return exported

def export_csv(tasks_file, date_from, date_to):
    """
    Export all tasks as CSV (one per entry) between date_from and date_to (inclusive).
    Skips tasks with duration 0 or ending with '**'.
    Columns: category, task, notes, finish (ISO), duration_minutes
    Returns the CSV as a string.
    """
    date_from_dt = datetime.datetime.combine(date_from, datetime.time.min)
    date_to_dt = datetime.datetime.combine(date_to, datetime.time.max)

    tasklog = read_tasklog(tasks_file)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["category", "task", "notes", "finish", "duration_minutes"])

    for entry in tasklog:
        if not (date_from_dt <= entry.finish <= date_to_dt):
            continue
        if entry.duration.total_seconds() == 0:
            continue
        if entry.task.endswith("**"):
            continue
        writer.writerow([
            entry.category,
            entry.task,
            entry.notes,
            entry.finish.isoformat(),
            int(entry.duration.total_seconds() // 60)
        ])
    return output.getvalue()