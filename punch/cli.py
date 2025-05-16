from argparse import ArgumentParser
import sys
from rich.console import Console

from punch.config import load_config
from punch.tasks import get_recent_tasks, write_task

def select_from_list(console, items, prompt, style="bold yellow"):
    """
    Helper to display a numbered list and prompt for selection.
    Returns the selected item or None if invalid.
    """
    for idx, item in enumerate(items):
        console.print(f"{idx + 1}. {item}", style=style)
    selected = console.input(prompt)
    try:
        selected_idx = int(selected) - 1
        if selected_idx < 0 or selected_idx >= len(items):
            raise ValueError("Invalid selection")
        return items[selected_idx]
    except ValueError:
        console.print("Invalid input. Please enter a number.", style="bold red")
        return None

def interactive_mode(categories, tasks_file):
    console = Console()
    # Convert dict to list of keys if needed
    if isinstance(categories, dict):
        category_list = list(categories.keys())
    else:
        category_list = categories

    console.print("Interactive mode", style="bold green")
    console.print("Available categories:", style="bold blue")
    selected_category = select_from_list(console, category_list, "Select a category by number: ")
    if selected_category is None:
        return

    tasks = get_recent_tasks(tasks_file, selected_category)
    task_names = [task.task for task in tasks]
    console.print(f"Recent tasks in {selected_category}:", style="bold blue")
    selected_task = select_from_list(
        console,
        task_names + ["New task"],
        "Select a task by number: "
    )
    if selected_task is None:
        return

    if selected_task == "New task":
        task_name = console.input("Enter new task name: ")
    else:
        task_name = selected_task

    notes = console.input("Enter notes (optional): ")
    write_task(tasks_file, selected_category, task_name, notes)
    console.print(f"Logged: {selected_category} : {task_name} : {notes}", style="bold green")

def prepare_parser():    
    parser = ArgumentParser(description="punch - a CLI tool for managing your tasks")
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s 1.0",
        help="Show the version of the program"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    parser_new = subparsers.add_parser("new", help="Mark the start of your day")

    parser_report = subparsers.add_parser("report", help="Print a report of your timecards")
    parser_report.add_argument(
        "-f", "--from", help="Specify the start date for the report (YYYY-MM-DD)"
    )
    parser_report.add_argument(
        "-t", "--to", help="Specify the end date for the report (YYYY-MM-DD)"
    )

    parser_export = subparsers.add_parser("export", help="Export your timecards")
    parser_export.add_argument(
        "-f", "--from", help="Specify the start date for the export (YYYY-MM-DD)"
    )
    parser_export.add_argument(
        "-t", "--to", help="Specify the end date for the export (YYYY-MM-DD)"
    )
    parser_export.add_argument(
        "--format", choices=["csv", "json"], help="Specify the format for export"
    )
    parser_export.add_argument(
        "-o", "--output", help="Specify the output file for export"
    )

    parser_login = subparsers.add_parser("login", help="Login to your timecards account")


    parser_submit = subparsers.add_parser("submit", help="Submit your timecards")
    parser_submit.add_argument(
        "-f", "--from", help="Specify the start date for the submission (YYYY-MM-DD)"
    )
    parser_submit.add_argument(
        "-t", "--to", help="Specify the end date for the submission (YYYY-MM-DD)"
    )
    parser_submit.add_argument(
        "-n", "--dry-run", action="store_true", help="Perform a dry run of the submission"
    )

    return parser

def main():
    config = load_config()
    tasks_file = config.get('tasks_file', 'tasks.txt')
    categories = config.get('categories', [])
    
    parser = prepare_parser()
    parser.parse_args()

    if len(sys.argv) == 1:
        interactive_mode(categories, tasks_file)