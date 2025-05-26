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
from punch.web import DRY_RUN_SUFFIX, get_timecards, login_to_site, submit_timecards, MissingTimecardsUrl


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

def escape_separators(s):
    """
    Escapes colons in the input string to avoid splitting on them,
    but only if the colon is not the first or last character.
    """
    if len(s) <= 2:
        return s
    # Replace ":" with "\:" only if not at the start or end
    return s[0] + s[1:-1].replace(":", r"\:") + s[-1]

def prepare_parser():    
    parser = ArgumentParser(description="punch - a CLI tool for managing your tasks")
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s 0.1.3",
        help="Show the version of the program"
    )

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
            # Format duration as H:MM (no seconds, no days)
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            duration_str = f"{hours}:{minutes:02d}"
            line = f"{left.ljust(max_left_len)} {duration_str.rjust(10)} ({minutes + hours*60} min)"
            cat_node.add(line)
            total_duration += duration

    total_minutes = int(total_duration.total_seconds() // 60)
    total_hours = int(total_duration.total_seconds() // 3600)
    remainder_minutes = total_minutes % 60
    # Print total as H:MM (not days)
    total_str = f"{total_hours}:{remainder_minutes:02d}"
    tree.add(f"[bold yellow]Total: {total_str.rjust(max_left_len+8)} ({total_minutes} min)[/bold yellow]")

    console.print(tree)

def show_timecards_table(timecards):
    """
    Display the timecards in a table format using rich.
    Expects timecards to be a list of dictionaries with keys:
    'date', 'category', 'task', 'notes', 'duration'.
    """
    from rich.table import Table
    from rich.console import Console

    console = Console()
    table = Table(title="Timecards for submission")

    table.add_column("Case no.", justify="center", style="cyan")
    table.add_column("Task", justify="left", style="magenta", max_width=50, no_wrap=True)
    table.add_column("Work performed", justify="left", style="green", max_width=50, no_wrap=True)
    table.add_column("Minutes", justify="right", style="yellow")
    table.add_column("Start time", justify="right", style="blue")

    for timecard in timecards:
        table.add_row(
            timecard.case_no,
            timecard.desc,
            timecard.work_performed,
            str(timecard.minutes),
            datetime.combine(
                timecard.start_date, timecard.start_time
            ).strftime("%Y-%m-%d %H:%M")
        )

    console.print(table)

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
            # Set the datetime to today with the time from args.time
            start_dt = None
            if args.time:
                now = datetime.now()
                start_dt = datetime.combine(now.date(), args.time)
            write_task(tasks_file, "", "start", "", start_dt)
        elif args.command == "help":
            parser.print_help()
        elif args.command == "add":
            quick_task = sys.argv[2:]
            task_str =  " ".join([escape_separators(s) for s in quick_task])
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
                if args.interactive:
                    args.headed = True  # --interactive implies --headed

                timecards = get_timecards(tasks_file, getattr(args, 'from'), args.to)
                if not timecards or len(timecards) == 0:
                    console.print("No timecards found for submission.", style="bold red")
                    return
                show_timecards_table(timecards)
                
                suffix = DRY_RUN_SUFFIX if args.dry_run else ""
                proceed = console.input(f"Proceed with submission?{suffix} (y/N): ").strip().lower()
                if proceed != "y":
                    console.print("Submission cancelled.", style="bold yellow")
                    return

                submit_timecards(timecards, headless=not args.headed, interactive=args.interactive, dry_run=args.dry_run)
            except MissingTimecardsUrl as e:
                console.print(f"[red]{e}[/red]")
                sys.exit(1)
