from datetime import datetime, time, timedelta
import os
import sys
from argparse import ArgumentParser
from rich.console import Console
from rich.tree import Tree

from punch.config import load_config, get_config_path, get_tasks_file
from punch.export import export_csv, export_json
from punch.tasks import get_recent_tasks, write_task, parse_new_task_string
from punch.report import generate_report
from punch.web import login_to_site, submit_timecards, MissingTimecardsUrl


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

def valid_date(date_str):
    """
    Validates the date format (YYYY-MM-DD).
    Returns a datetime.date object if valid, raises ValueError otherwise.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")

def prepare_parser():    
    parser = ArgumentParser(description="punch - a CLI tool for managing your tasks")
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s 1.0",
        help="Show the version of the program"
    )

    today_str = datetime.now().strftime("%Y-%m-%d")

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=False)

    parser_start = subparsers.add_parser("start", help="Login to your timecards account")

    parser_report = subparsers.add_parser("report", help="Print a report of your timecards")
    parser_report.add_argument(
        "-f", "--from", default=today_str, type=valid_date, help="Specify the start date for the report (YYYY-MM-DD)"
    )
    parser_report.add_argument(
        "-t", "--to", default=today_str, type=valid_date, help="Specify the end date for the report (YYYY-MM-DD)"
    )

    parser_export = subparsers.add_parser("export", help="Export your timecards")
    parser_export.add_argument(
        "-f", "--from", default=today_str, type=valid_date, help="Specify the start date for the export (YYYY-MM-DD)"
    )
    parser_export.add_argument(
        "-t", "--to", default=today_str, type=valid_date, help="Specify the end date for the export (YYYY-MM-DD)"
    )
    parser_export.add_argument(
        "--format", choices=["csv", "json"], default="json", help="Specify the format for export"
    )
    parser_export.add_argument(
        "-o", "--output", help="Specify the output file for export"
    )

    parser_add = subparsers.add_parser("add", help="Add a new task")
    parser_add.add_argument(
        "task_args",
        nargs="+",
        help="Category, colon, task, and optional notes (e.g. c : Task name : Notes)"
    )

    parser_login = subparsers.add_parser("login", help="Login to your timecards account")

    parser_submit = subparsers.add_parser("submit", help="Submit your timecards")
    parser_submit.add_argument(
        "-f", "--from", default=today_str, type=valid_date, help="Specify the start date for the submission (YYYY-MM-DD)"
    )
    parser_submit.add_argument(
        "-t", "--to", default=today_str, type=valid_date, help="Specify the end date for the submission (YYYY-MM-DD)"
    )
    parser_submit.add_argument(
        "-n", "--dry-run", action="store_true", help="Perform a dry run of the submission"
    )
    parser_submit.add_argument(
        "--headed", action="store_true", help="Run the browser in headed mode"
    )

    return parser

def print_report(report):
    """
    Pretty-print the report dictionary using a rich Tree.
    The report dict should be in the format:
      {category: [(task, duration)]} if collapsed,
      or {category: [(task, notes, duration)]} if not collapsed.
    Also prints the sum of all durations at the bottom.
    """
    console = Console()
    tree = Tree("Task Report")

    # Find max length for left part (task or task | notes)
    max_left_len = 0
    for entries in report.values():
        for entry in entries:
            if len(entry) == 2:
                task = entry[0]
                left = f"{task}"
            elif len(entry) == 3:
                task, notes, _ = entry
                left = f"{task}"
                if notes:
                    left += f" | {notes}"
            max_left_len = max(max_left_len, len(left))

    total_duration = timedelta(0)

    for category, entries in report.items():
        cat_node = tree.add(f"[bold]{category}[/bold]")
        for entry in entries:
            if len(entry) == 2:
                # collapsed: (task, duration)
                task, duration = entry
                minutes = int(duration.total_seconds() // 60)
                left = f"{task}"
            elif len(entry) == 3:
                # not collapsed: (task, notes, duration)
                task, notes, duration = entry
                minutes = int(duration.total_seconds() // 60)
                left = f"{task}"
                if notes:
                    left += f" | {notes}"
            # Pad left part so all durations align
            line = f"{left.ljust(max_left_len)} {str(duration).rjust(10)} ({minutes} min)"
            cat_node.add(line)
            total_duration += duration

    total_minutes = int(total_duration.total_seconds() // 60)
    tree.add(f"[bold yellow]Total: {str(total_duration).rjust(max_left_len+8)} ({total_minutes} min)[/bold yellow]")

    console.print(tree)

def main():
    config_path = get_config_path()
    if not os.path.exists(config_path):
        # If config does not exist, create directory and empty config
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            f.write("categories: []\n")
    config = load_config(config_path)
    tasks_file = get_tasks_file()
    categories = config.get('categories', [])
    console = Console()

    # If no arguments, enter interactive mode
    if len(sys.argv) == 1:
        interactive_mode(categories, tasks_file)
        return
    else:
        parser = prepare_parser()
        args = parser.parse_args()
        
        if args.command == "start":
            write_task(tasks_file, "", "start", "")
        elif args.command == "add":
            quick_task = sys.argv[2:]
            task_str =  " ".join(quick_task)
            task = parse_new_task_string(task_str, categories)
            write_task(tasks_file, task.category, task.task, task.notes)
            print(f"Logged: {task.category} : {task.task} : {task.notes}")
        elif args.command == "report":
            # Implement report logic
            console.print(f"From: {getattr(args, 'from')} To: {getattr(args, 'to')}", style="bold blue")
            report = generate_report(tasks_file, getattr(args, 'from'), args.to)
            print_report(report)
        elif args.command == "export":
            if args.format == "json":
                print(export_json(tasks_file, getattr(args, 'from'), args.to))
            elif args.format == "csv":
                print(export_csv(tasks_file, getattr(args, 'from'), args.to))
        elif args.command == "login":
            try:
                login_to_site()
            except MissingTimecardsUrl as e:
                console.print(f"[red]{e}[/red]")
                sys.exit(1)
        elif args.command == "submit":
            try:
                submit_timecards(
                    tasks_file,
                    headless=not args.headed,
                    date_from=getattr(args, 'from', None),
                    date_to=getattr(args, 'to', None)
                )
            except MissingTimecardsUrl as e:
                console.print(f"[red]{e}[/red]")
                sys.exit(1)
