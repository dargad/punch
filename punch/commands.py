from datetime import datetime, timedelta
import os
import sys
from rich.console import Console
from rich.tree import Tree
from rich.syntax import Syntax
import yaml

from playwright.sync_api import TimeoutError

from punch.config import set_config_value
from punch.export import export_csv, export_json
from punch.report import generate_report
from punch.tasks import parse_new_task_string, write_task
from punch.web import DRY_RUN_SUFFIX, AuthFileNotFoundError, MissingTimecardsUrl, NoCaseMappingError, get_timecards, login_to_site, submit_timecards

def escape_separators(s):
    """
    Escapes colons in the input string to avoid splitting on them,
    but only if the colon is not the first or last character.
    """
    if len(s) <= 2:
        return s
    # Replace ":" with "\:" only if not at the start or end
    return s[0] + s[1:-1].replace(":", r"\:") + s[-1]

def show_config(config):
    """
    Pretty-print the loaded config as YAML.
    """
    from rich.syntax import Syntax

    console = Console()
    yaml_str = yaml.dump(config, sort_keys=False, allow_unicode=True)
    syntax = Syntax(yaml_str, "yaml", theme="ansi_dark", line_numbers=False)
    console.print(syntax)

def prompt_with_hint(console, prompt, current_value):
    """
    Prompt the user with a hint of the current value.
    Returns the new value or the current value if input is empty.
    """
    value = console.input(f"{prompt}{f' [{current_value!r}]' if current_value else ''}: ").strip()
    return value if value else current_value

def prompt_category(console, existing_short=None, existing_name=None, existing_caseid=None):
    """
    Prompt for a single category's details.
    Returns (short, name, caseid) or (None, None, None) if user is done.
    """
    short = console.input(
        f"  Short code (e.g. 'dev', 'mtg'){f' [{existing_short}]' if existing_short else ''} [leave empty to finish]: "
    ).strip()
    if not short:
        return None, None, None

    # Require non-empty category name
    while True:
        name = console.input(
            f"[{short!r}]  Full category name{f' [{existing_name}]' if existing_name else ''}: "
        ).strip()
        if name:
            break
        elif existing_name:
            name = existing_name
            break
        else:
            console.print("[red]Category name cannot be empty.[/red]")

    # Prompt for caseid, repeat if not a number (allow empty to skip)
    while True:
        caseid = console.input(
            f"[{short!r}]  Case id to file timecards against"
            f"{f' [{existing_caseid}]' if existing_caseid else ''} (leave empty to skip): "
        ).strip()
        if not caseid and existing_caseid:
            caseid = existing_caseid
            break
        if not caseid:
            caseid = None
            break
        if caseid.isdigit():
            caseid = caseid.zfill(8)
            break
        else:
            console.print("[red]Case id must be a number or empty.[/red]")
    return short, name, caseid

def print_existing_categories(console, categories):
    if categories:
        console.print("[yellow]Existing categories:[/yellow]")
        for name, cat in categories.items():
            short = cat.get("short", "")
            caseid = cat.get("caseid", "")
            console.print(f"  [cyan]{short}[/cyan]: {name}" + (f" (caseid: {caseid})" if caseid else ""))

def run_config_wizard(config, config_path):
    """
    Interactively prompt the user for config values and update the config file.
    """
    from ruamel.yaml import YAML
    yaml_ruamel = YAML()
    yaml_ruamel.preserve_quotes = True

    console = Console()
    console.print("[bold green]Welcome to the Punch configuration wizard![/bold green]")

    # Full name
    current_full_name = config.get("full_name", "")
    config["full_name"] = prompt_with_hint(console, "Enter your full name", current_full_name)

    # Timecards submissions link
    current_url = config.get("timecards_url", "")
    config["timecards_url"] = prompt_with_hint(console, "Enter the new timecard link (URL)", current_url)

    date_format = config.get("date_format", "%d/%m/%Y")
    config["date_format"] = prompt_with_hint(console, "Enter the timecard date format", date_format)

    # Timecards rounding
    current_round = config.get("timecards_round", 0)
    while True:
        round_str = prompt_with_hint(
            console,
            "Round tracked time to nearest <X> minutes (set to 0 to disable rounding)",
            current_round
        )
        try:
            config["timecards_round"] = int(round_str)
            break
        except (TypeError, ValueError):
            console.print("[red]Please enter a valid integer for rounding.[/red]")

    # Categories
    # Load existing categories as a dict (name -> entry)
    categories = {}
    existing_categories = config.get("categories", {})
    if isinstance(existing_categories, dict):
        categories.update(existing_categories)
    elif isinstance(existing_categories, list):
        for cat in existing_categories:
            name = cat.get("name") or cat.get("category") or cat.get("short")
            if name:
                categories[name] = cat

    console.print("Let's add your categories. Enter each category's details. Leave short code empty to finish.")
    print_existing_categories(console, categories)

    # Add new categories, don't replace existing
    while True:
        short, name, caseid = prompt_category(console)
        if not short:
            break
        cat_entry = {"short": short}
        if caseid:
            cat_entry["caseid"] = caseid
        categories[name] = cat_entry
        console.print()

    if categories:
        config["categories"] = categories

    # Save config with comments/whitespace preserved if possible
    if YAML is not None:
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    data = yaml_ruamel.load(f)
                if data is None:
                    data = {}
            else:
                data = {}
            data.update(config)
            with open(config_path, "w") as f:
                yaml_ruamel.dump(data, f)
        except Exception as e:
            console.print(f"[red]Failed to save config with formatting: {e}[/red]")
            with open(config_path, "w") as f:
                yaml.dump(config, f, sort_keys=False, allow_unicode=True)
    else:
        with open(config_path, "w") as f:
            yaml.dump(config, f, sort_keys=False, allow_unicode=True)

    console.print(f"[bold green]Configuration saved to {config_path}[/bold green]")

def handle_start(args, tasks_file):
    start_dt = None
    if args.time:
        now = datetime.now()
        start_dt = datetime.combine(now.date(), args.time)
    write_task(tasks_file, "", "start", "", start_dt)

def handle_help(parser):
    parser.print_help()

def handle_add(args, categories, tasks_file, console):
    quick_task = sys.argv[2:]
    task_str = " ".join([escape_separators(s) for s in quick_task])
    try:
        task = parse_new_task_string(task_str, categories)
        write_task(tasks_file, task.category, task.task, task.notes)
        print(f"Logged: {task.category} : {task.task} : {task.notes}")
    except ValueError as e:
        console.print(f"Error: {e}")
        sys.exit(1)

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

def handle_report(args, tasks_file, console):
    console.print(f"From: {getattr(args, 'from_')} To: {args.to}", style="bold blue")
    try:
        report = generate_report(tasks_file, getattr(args, 'from_'), args.to)
        print_report(report)
    except ValueError as e:
        console.print(f"Error generating report: {e}", style="bold red")

def handle_export(args, tasks_file, console):
    exported_content = None
    if args.format == "json":
        exported_content = export_json(tasks_file, getattr(args, 'from_'), args.to)
    elif args.format == "csv":
        exported_content = export_csv(tasks_file, getattr(args, 'from_'), args.to)
    if args.output:
        with open(args.output, "w") as f:
            f.write(exported_content)
        console.print(f"Exported to {args.output}", style="bold green")
    else:
        console.print(exported_content)

def handle_login(args, config, console):
    try:
        login_to_site(config, args.verbose)
    except MissingTimecardsUrl as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

def show_timecards_table(timecards):
    """
    Display the timecards in a table format using rich.
    """
    from rich.table import Table
    from rich.console import Console
    
    console = Console()
    table = Table(title="Timecards for submission", show_footer=True)

    table.add_column("Case no.", justify="center", style="cyan")
    table.add_column("Task", justify="left", style="magenta", max_width=50, no_wrap=True)
    table.add_column("Work performed", justify="left", style="green", max_width=50, no_wrap=True)
    table.add_column("Minutes", justify="right", style="yellow")
    table.add_column("Start time", justify="right", style="blue")

    total_minutes = 0
    for tc in timecards:
        minutes = int(getattr(tc, "minutes", 0) or 0)
        total_minutes += minutes
        table.add_row(
            str(getattr(tc, "case_no", "")),
            str(getattr(tc, "desc", "")),
            str(getattr(tc, "work_performed", "")),
            str(minutes),
            datetime.combine(
                getattr(tc, "start_date"), getattr(tc, "start_time")
            ).strftime("%Y-%m-%d %H:%M"),
        )

    # Footer: label + total in the Minutes column
    table.columns[2].footer = "Total"
    table.columns[3].footer = str(total_minutes)

    console.print(table)

def handle_submit(args, config, tasks_file, console):
    try:
        if args.interactive:
            args.headed = True  # --interactive implies --headed

        timecards = []
        try:
            timecards = get_timecards(config, tasks_file, getattr(args, 'from_'), args.to)
        except AuthFileNotFoundError as e:
            console.print("[red]Auth info file not found. Please login first using the 'login' command.[/red]")
            return
        except NoCaseMappingError as e:
            console.print(f"[red]{e}[/red]")
            return

        if not timecards or len(timecards) == 0:
            console.print("No timecards found for submission.", style="bold red")
            return
        show_timecards_table(timecards)
        
        suffix = DRY_RUN_SUFFIX if args.dry_run else ""
        proceed = console.input(f"Proceed with submission?{suffix} (y/N): ").strip().lower()
        if proceed != "y":
            console.print("Submission cancelled.", style="bold yellow")
            return

        submit_timecards(
            config,
            timecards,
            headless=not args.headed,
            interactive=args.interactive,
            dry_run=args.dry_run,
            verbose=args.verbose,
            sleep=args.sleep
        )

    except TimeoutError:
        console.print("[red]Submission timed out. Please retry logging in with `punch login`[/red]")
        sys.exit(1)

    except MissingTimecardsUrl as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

def handle_config(args, config, config_path, console):
    if args.config_command == "path":
        console.print(f"{config_path}", style="bold blue")
    elif args.config_command == "show":
        show_config(config)
    elif args.config_command == "edit":
        os.system(f"{os.getenv('EDITOR', 'vi')} {config_path}")
    elif args.config_command == "set":
        if args.option and args.value:
            set_config_value(config, config_path, args.option, args.value)
        else:
            console.print("Please provide both key and value to set.", style="bold red")
    elif args.config_command == "get":
        if args.option:
            value = config.get(args.option)
            if value is not None:
                console.print(f"{value}")
            else:
                console.print(f"Key '{args.option}' not found in config.", style="bold red")
        else:
            console.print("Please provide a key to get its value.", style="bold red")
    elif args.config_command == "wizard":
        run_config_wizard(config, config_path)
    else:
        show_config(config)