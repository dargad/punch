from datetime import datetime, time, timedelta
import os
import sys
from argparse import ArgumentParser
import yaml
from rich.console import Console

from punch.commands import handle_add, handle_config, handle_export, handle_help, handle_login, handle_report, handle_start, handle_submit
from punch.config import get_config_path, get_tasks_file, load_config
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
        "-V", "--version", action="version", version="%(prog)s 0.1.3",
        help="Show the version of the program"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    today_str = datetime.now().strftime("%Y-%m-%d")

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=False)

    parser_start = subparsers.add_parser("start", help="Mark the start of your workday")
    parser_start.add_argument(
        "-t", "--time", type=lambda s: datetime.strptime(s, "%H:%M").time(), help="Specify the start time (HH:MM)"
    )

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

    parser_help = subparsers.add_parser("help", help="Show this help message")

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
    parser_submit.add_argument(
        "-i", "--interactive", action="store_true", help="Run in interactive mode (punch fills the form you click 'Save & New'). Implies --headed."
    )
    parser_submit.add_argument(
        "--sleep", type=float, default=0, help="Sleep for X seconds after filling out the form"
    )

    parser_config = subparsers.add_parser("config", help="Show the current configuration")
    config_subparsers = parser_config.add_subparsers(dest="config_command", help="Config subcommands")
    config_subparsers.add_parser("path", help="Show the path of current configuration file")
    config_subparsers.add_parser("show", help="Show the current configuration")
    config_subparsers.add_parser("edit", help="Edit the configuration file")

    parser_set = config_subparsers.add_parser("set", help="Set config file option")
    parser_set.add_argument("option", help="Option name to set")
    parser_set.add_argument("value", help="Value to set for the option")

    parser_get = config_subparsers.add_parser("get", help="Get value of a config file option")
    parser_get.add_argument("option", help="Option name to get")

    config_subparsers.add_parser("wizard", help="Run the configuration wizard to set up your config")

    return parser

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
            handle_start(args, tasks_file)
        elif args.command == "help":
            handle_help(parser)
        elif args.command == "add":
            handle_add(args, categories, tasks_file, console)
        elif args.command == "report":
            handle_report(args, tasks_file, console)
        elif args.command == "export":
            handle_export(args, tasks_file, console)
        elif args.command == "login":
            handle_login(args, config, console)
        elif args.command == "submit":
            handle_submit(args, config, tasks_file, console)
        elif args.command == "config":
            handle_config(args, config, config_path, console)
