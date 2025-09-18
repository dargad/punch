from datetime import date, datetime
from importlib.metadata import version
from importlib.resources import files
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Optional
import typer
import dateparser
import yaml
from rich.console import Console

from punch.commands import escape_separators, get_category_by_short, handle_add, handle_export, handle_help, handle_login, handle_report, handle_start, handle_submit, time_to_current_datetime
from punch.config import get_config_path, get_tasks_file, load_config
from punch.tasks import CMDLINE_SEPARATOR, get_recent_tasks, write_task
from punch import __version__, _DISTRIBUTION

app = typer.Typer(help="punch - a CLI tool for managing your tasks")
config_app = typer.Typer(help="Manage configuration options.")
app.add_typer(config_app, name="config")

def check_human_date(value: str) -> str:
    if not value:
        return ""
    try:
        dt = dateparser.parse(value)
        if dt is None:
            raise typer.BadParameter(f"Invalid date format: {value!r}")
        return dt.date().strftime("%x")
    except Exception as e:
        raise typer.BadParameter(f"Invalid date format: {value!r}") from e
    
def human_date(value: str) -> date:
    try:
        dt = dateparser.parse(value)
        if dt is None:
            raise typer.BadParameter(f"Invalid date format: {value!r}")
        return dt.date()
    except Exception as e:
        raise typer.BadParameter(f"Invalid date format: {value!r}") from e

def check_valid_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date().strftime("%Y-%m-%d")
    except ValueError:
        raise typer.BadParameter("Invalid date format. Use YYYY-MM-DD.")
    
def valid_date(date_str: str) -> date:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise typer.BadParameter("Invalid date format. Use YYYY-MM-DD.")

def select_from_list(console, items, prompt, style="bold yellow"):
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

def interactive_mode(categories, tasks_file, selected_category=None):
    console = Console()
    if isinstance(categories, dict):
        category_list = list(categories.keys())
    else:
        category_list = categories

    console.print("Interactive mode", style="bold green")

    if not selected_category in category_list:
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

def read_changelog() -> str:
    snap = os.getenv("SNAP")
    if snap:
        p = Path(snap) / "usr/share/punch/CHANGELOG.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
    # fallback: jeśli dodałeś też include = ["CHANGELOG.md"] w Poetry
    from importlib.resources import files
    return (files("punch").parent / "CHANGELOG.md").read_text(encoding="utf-8")

def current_version() -> str:
    return os.getenv("SNAP_VERSION") or (version(_DISTRIBUTION) if not os.getenv("SNAP") else "0.0.0")

def user_state_path() -> Path:
    base = Path(os.getenv("SNAP_USER_DATA") or Path.home() / ".config" / _DISTRIBUTION)
    base.mkdir(parents=True, exist_ok=True)
    return base / "state.json"

def load_state():
    p = user_state_path()
    if p.exists():
        try:
            return json.loads(p.read_text() or "{}")
        except Exception:
            return {}
    return {}

def save_state(state):
    user_state_path().write_text(json.dumps(state))

def should_show_news(cv: str) -> bool:
    if not sys.stdout.isatty():
        return False
    if os.getenv(f"{_DISTRIBUTION.upper()}_NO_NEWS") == "1":
        return False
    st = load_state()
    return st.get("last_seen_version") != cv

def mark_seen(cv: str):
    st = load_state()
    st["last_seen_version"] = cv
    save_state(st)

def show_teaser(cv: str):
    typer.secho(f"🔹 New version: {cv}. Try '{_DISTRIBUTION} whats-new' to read more.", dim=True)

@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """
    punch - a CLI tool for managing your tasks
    """
    cv = __version__
    if should_show_news(cv):
        show_teaser(cv)
        mark_seen(cv)

    config_path = get_config_path()
    if not os.path.exists(config_path):
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            f.write("categories: []\n")
    config = load_config(config_path)
    tasks_file = get_tasks_file()
    categories = config.get('categories', [])

    if ctx.invoked_subcommand is None:
        interactive_mode(categories, tasks_file)
        raise typer.Exit()

@app.command()
def start(
    time: str = typer.Option(None, "-t", "--time", help="Specify the start time (HH:MM)"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """
    Mark the start of your day.
    """
    tasks_file = get_tasks_file()
    
    handle_start(SimpleNamespace(time=time_to_current_datetime(time) if time else None, verbose=verbose), tasks_file)

@app.command()
def add(
    time: str = typer.Option(None, "-t", "--time", help="Specify the start time (HH:MM)"),
    task_args: list[str] = typer.Argument(..., help="<category> : <task> [: <notes>] (e.g. c : Task name : Notes)"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """
    Add a new task.
    """
    config = load_config(get_config_path())
    categories = config.get('categories', {})
    tasks_file = get_tasks_file()
    console = Console()

    task_str = " ".join([escape_separators(s) for s in task_args])

    if CMDLINE_SEPARATOR not in task_str:
        try:
            name, cat = get_category_by_short(categories, task_str)
            if cat:
                interactive_mode(categories, tasks_file, name)
                return
        except ValueError as e:
            pass

    handle_add(
        SimpleNamespace(task_str=task_str, verbose=verbose,
                        time=time_to_current_datetime(time) if time else None),
        categories,
        tasks_file,
        console
   )

def resolve_date_range(day: Optional[str], from_date: Optional[str], to_date: Optional[str], ctx_name: str = "report"):
    """
    Validate and resolve day/from_date/to_date logic for report/export/submit commands.
    Returns (day, from_date, to_date) as date objects.
    Raises Typer.Exit on invalid input.
    """
    # Mutual exclusivity
    if day and (from_date or to_date):
        typer.secho(f"Use either --day OR --from/--to, not both in {ctx_name}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Range rules
    if to_date and not from_date:
        typer.secho(f"If you pass --to, you must also pass --from in {ctx_name}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Convert to date objects
    day_obj = human_date(day) if day else None
    from_obj = valid_date(from_date) if from_date else None
    to_obj = valid_date(to_date) if to_date else None

    if from_obj and to_obj and from_obj > to_obj:
        typer.secho(f"--from cannot be after --to in {ctx_name}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if day_obj:
        from_obj = to_obj = day_obj
    elif from_obj and not to_obj:
        to_obj = date.today()
    
    if not day_obj and not from_obj and not to_obj:
        day_obj = from_obj = to_obj = date.today()

    return day_obj, from_obj, to_obj

@app.command()
def report(
    day: Optional[str] = typer.Option(
        None, "-d", "--day", help="Generate report for a single day",
        callback=check_human_date
    ),
    from_date: Optional[str] = typer.Option(
        None, "-f", "--from", help="Start date for the report.",
        callback=check_valid_date
    ),
    to_date: Optional[str] = typer.Option(
        None, "-t", "--to", help="End date for the report (defaults to today if --from is given).",
        callback=check_valid_date
    ),
):
    """
    Show report for a specific day or date range.
    """
    day_obj, from_obj, to_obj = resolve_date_range(day, from_date, to_date, ctx_name="report")
    parser_args = SimpleNamespace(day=day_obj, from_=from_obj, to=to_obj)
    tasks_file = get_tasks_file()
    console = Console()
    handle_report(parser_args, tasks_file, console)

@app.command()
def export(
    day: str = typer.Option(None, "-d", "--day", help="Specify a single day for the report (sets --from and --to to this date)", callback=check_human_date),
    from_: str = typer.Option(None, "-f", "--from", help="Specify the start date for the export (YYYY-MM-DD)", callback=check_valid_date),
    to: str = typer.Option(None, "-t", "--to", help="Specify the end date for the export (YYYY-MM-DD)", callback=check_valid_date),
    format: str = typer.Option("json", "--format", help="Specify the format for export", show_choices=True, case_sensitive=False),
    output: str = typer.Option(None, "-o", "--output", help="Specify the output file for export"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """
    Export tasks for a specific day or date range.
    """
    day_obj, from_obj, to_obj = resolve_date_range(day, from_, to, ctx_name="export")
    parser_args = SimpleNamespace(day=day_obj, from_=from_obj, to=to_obj, format=format, output=output, verbose=verbose)
    tasks_file = get_tasks_file()
    console = Console()
    handle_export(parser_args, tasks_file, console)

@app.command()
def login(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """
    Log in to SF and store your session locally.
    """
    config = load_config(get_config_path())
    console = Console()
    handle_login(SimpleNamespace(verbose=verbose), config, console)

@app.command()
def submit(
    day: str = typer.Option(None, "-d", "--day", help="Specify a single day for the report (sets --from and --to to this date)", callback=check_human_date),
    from_: str = typer.Option(None, "-f", "--from", help="Specify the start date for the submission (YYYY-MM-DD)", callback=check_valid_date),
    to: str = typer.Option(None, "-t", "--to", help="Specify the end date for the submission (YYYY-MM-DD)", callback=check_valid_date),
    dry_run: bool = typer.Option(False, "-n", "--dry-run", help="Perform a dry run of the submission"),
    headed: bool = typer.Option(False, "--headed", help="Run the browser in headed mode"),
    interactive: bool = typer.Option(False, "-i", "--interactive", help="Run in interactive mode (implies --headed)"),
    sleep: float = typer.Option(0, "--sleep", help="Sleep for X seconds after filling out the form"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """
    Submit timecards for a specific day or date range to SF.
    """
    day_obj, from_obj, to_obj = resolve_date_range(day, from_, to, ctx_name="submit")
    parser_args = SimpleNamespace(day=day_obj, from_=from_obj, to=to_obj, dry_run=dry_run, headed=headed, interactive=interactive, sleep=sleep, verbose=verbose)
    config = load_config(get_config_path())
    tasks_file = get_tasks_file()
    console = Console()
    handle_submit(parser_args, config, tasks_file, console)

@config_app.command("show")
def config_show(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """Show the current configuration."""
    config_path = get_config_path()
    config_data = load_config(config_path)
    console = Console()
    from punch.commands import show_config
    show_config(config_data)

@config_app.command("edit")
def config_edit(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """Edit the configuration file in $EDITOR."""
    config_path = get_config_path()
    os.system(f"{os.getenv('EDITOR', 'vi')} {config_path}")

@config_app.command("path")
def config_path_cmd(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """Show the path to the configuration file."""
    config_path = get_config_path()
    typer.echo(config_path)

@config_app.command("set")
def config_set(
    option: str = typer.Argument(..., help="Option name to set"),
    value: str = typer.Argument(..., help="Value to set"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """Set a configuration value."""
    config_path = get_config_path()
    config_data = load_config(config_path)
    from punch.config import set_config_value
    set_config_value(config_data, config_path, option, value)
    typer.echo(f"Set {option} to {value}")

@config_app.command("get")
def config_get(
    option: str = typer.Argument(..., help="Option name to get"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """Get a configuration value."""
    config_path = get_config_path()
    config_data = load_config(config_path)
    value = config_data.get(option)
    if value is not None:
        typer.echo(value)
    else:
        typer.echo(f"Key '{option}' not found in config.")

@config_app.command("wizard")
def config_wizard(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
):
    """Run the interactive configuration wizard."""
    config_path = get_config_path()
    config_data = load_config(config_path)
    from punch.commands import run_config_wizard
    run_config_wizard(config_data, config_path)
@app.command("help")
def help_cmd(
    ctx: typer.Context,
    command: Optional[list[str]] = typer.Argument(
        None,
        help="Show help for this app or a subcommand path, e.g. `help greet` or `help tools sub`.",
    ),
):
    """Show the same help text as `--help`."""
    # `ctx` here is the context of the `help` command. Its parent is the app context.
    if not command:
        # Root help (same as `myprog --help`)
        typer.echo(ctx.parent.get_help())
        raise typer.Exit()

    # Resolve a nested command path (e.g. ["tools", "build"])
    cmd = ctx.parent.command  # start at the app (click.MultiCommand)
    target = None
    info_parts: list[str] = []

    for name in command:
        info_parts.append(name)
        target = cmd.get_command(ctx.parent, name)  # click API
        if target is None:
            typer.secho(f"Unknown command: {' '.join(info_parts)}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        cmd = target  # descend

    # Show help for the resolved command
    with typer.Context(target, info_name=" ".join(info_parts), parent=ctx.parent) as subctx:
        typer.echo(target.get_help(subctx))
    raise typer.Exit()

@app.command("whats-new")
def whats_new():
    """
    Show changes to the current version.
    """
    console = Console()
    changelog = read_changelog()
    current_ver = __version__
    text = ""

    if current_ver:
        out = []
        copy = False
        for line in changelog.splitlines():
            if line.startswith("## ") and current_ver in line:
                copy = True
            elif line.startswith("#") and copy:
                break
            if copy:
                out.append(line)
        text = "\n".join(out) or f"Version not found ini changelog: {current_ver}."
    
    console.print(text)

if __name__ == "__main__":
    app()
