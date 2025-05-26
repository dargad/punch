from dataclasses import dataclass
import os
import time
from playwright.sync_api import sync_playwright, Error as playwright_error
from punch.tasks import read_tasklog
import datetime
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.console import Console
import re
from punch.config import get_config_path, load_config
import sys

DRY_RUN_SUFFIX = " (dry run)"

@dataclass
class TimecardEntry:
    case_no: str
    owner: str
    minutes: int
    start_date: datetime.date
    start_time: datetime.time
    work_performed: str
    desc: str

class MissingTimecardsUrl(Exception):
    pass

def get_timecards_link():
    """
    Fetch the timecards link from config, or raise if not set.
    """
    config_path = get_config_path()
    config = load_config(config_path)
    url = config.get("timecards_url")
    if not url:
        raise MissingTimecardsUrl("No timecards_url found in config. Please set it in your config file.")
    return url

def get_auth_json_path():
    config_path = get_config_path()
    config_dir = os.path.dirname(config_path)
    auth_dir = config_dir
    os.makedirs(auth_dir, exist_ok=True)
    return os.path.join(auth_dir, "auth.json")

def log_redirects(request):
    from rich.console import Console
    console = Console()
    if request.redirected_from:
        console.print(
            f"[yellow]Redirected from[/yellow] [cyan]{request.redirected_from.url}[/cyan] [yellow]to[/yellow] [cyan]{request.url}[/cyan]"
        )

def login_to_site(verbose=False):
    console = Console()
    auth_json_path = get_auth_json_path()
    timecards_link = get_timecards_link()
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False)
        if os.path.exists(auth_json_path):
            context = browser.new_context(storage_state=auth_json_path)
            console.print("[cyan]Loaded existing authentication from auth.json[/cyan]")
        else:
            context = browser.new_context()
            console.print("[yellow]No auth.json found, starting fresh browser session[/yellow]")
        page = context.new_page()
        if verbose:
            page.on("request", log_redirects)

        console.print(f"[cyan]Opening login page: {timecards_link}[/cyan]")
        page.goto(timecards_link)

        console.print(f"[cyan]Waiting for login at {timecards_link}...[/cyan]")
        page.wait_for_url(timecards_link, timeout=30000)
        console.print("[green]Login successful.[/green]")

        context.storage_state(path=auth_json_path)
        console.print("[green]Login saved to auth.json[/green]")

        browser.close()

def select_from_combo(page, value, placeholder, xpath):
    """
    Select an item from a Lightning combobox by filling the input, clicking, and selecting the matching element.
    """
    input_box = page.locator(f'input[placeholder="{placeholder}"]')
    input_box.fill(f"{value}")
    time.sleep(1)
    input_box.click()
    element = page.locator(xpath)
    element.wait_for(state="visible", timeout=10000)
    
    element.click()

    time.sleep(1)

def determine_case_number(entry):
    """
    Returns the case number for the entry's category using the config file.
    Looks up entry.category in config['categories'][<category>]['caseid'].
    Left-fills the result with zeroes to 8 characters.
    Returns None if not found.
    """
    config_path = get_config_path()
    config = load_config(config_path)
    categories = config.get("categories", {})
    if not isinstance(categories, dict):
        return None
    cat_info = categories.get(entry.category)
    if not cat_info or "caseid" not in cat_info:
        return None
    caseid = str(cat_info["caseid"]).zfill(8)
    return caseid

def extract_case_number(task):
    """
    Extracts the case number from the task name.
    Supported formats:
      - "[XXXXXXXX] " (square brackets, up to 8 digits)
      - "SF#XXXXXXXX" (SF# prefix, up to 8 digits)
    Returns the case number as a string, left-filled to 8 characters with '0'.
    Returns None if not found.
    """
    # Match [XXXXXXXX]
    match = re.search(r"\[(\d{1,8})\]", task)
    if match:
        return match.group(1).zfill(8)
    # Match SF#XXXXXXXX
    match = re.search(r"SF#(\d{1,8})", task)
    if match:
        return match.group(1).zfill(8)
    return None

def _convert_to_timecard(entry):
    case_no = determine_case_number(entry)

    # Fetch full name from config
    config_path = get_config_path()
    config = load_config(config_path)
    full_name = config.get("full_name")
    if not full_name:
        raise Exception("Full name not set in config file. Please add 'full_name' to your config.")

    if not case_no:
        # if no case number mapping found try to extract it from the task
        case_no = extract_case_number(entry.task)
        desc = entry.notes if hasattr(entry, "notes") else entry.task
    else:
        # if mapping has been found use taskname as notes
        desc = entry.task

    duration = int(entry.duration.total_seconds() // 60)
    start_time = entry.finish - datetime.timedelta(minutes=duration)

    return TimecardEntry(
        case_no, 
        full_name, 
        duration, 
        start_time.date(), 
        start_time.time(), 
        desc, 
        entry.task
    )

def get_timecards(file_path="tasks.txt", date_from=None, date_to=None):
    """
    Returns a list of TimecardEntry objects for tasks between date_from and date_to (inclusive).
    date_from and date_to should be datetime.date objects or None (defaults to all).
    """
    entries = _get_valid_entries(Console(), file_path, None, date_from, date_to)
    if not entries:
        return []
    return [_convert_to_timecard(entry) for entry in entries]

def submit_timecards(timecards, headless=True, interactive=False, dry_run=False, verbose=False):
    """
    Submits timecards for tasks between date_from and date_to (inclusive).
    date_from and date_to should be datetime.date objects or None (defaults to all).
    """

    if not timecards or len(timecards) == 0:
        console.print("[yellow]No timecards to submit.[/yellow]")
        return

    console = Console()
    auth_json_path = get_auth_json_path()
    suffix = DRY_RUN_SUFFIX if dry_run else ""
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=headless)
        context = _get_browser_context(console, browser, auth_json_path)
        if context is None:
            return

        page = context.new_page()
        if verbose:
            page.on("request", log_redirects)
        
        if _login_to_timecards(console, page):
            console.print(f"[green]Login successful. Submitting timecards...[/green]{suffix}")

        try:
            _submit_entries_with_progress(console, page, timecards, interactive, dry_run)
        except playwright_error:
            console.print("[red]The browser window was closed before submission could complete.[/red]")
            return

        if not interactive:
            _cancel_edit(page)
            console.print(f"[bold green]Submitted {len(timecards)} entries.{suffix}[/bold green]")
            browser.close()
        else:
            console.print("[yellow]Interactive mode enabled. Please review the entries before submitting.[/yellow]")
            console.print("[yellow]Close the browser window when done.[/yellow]")
            page.wait_for_event("close", timeout=0)

def _get_browser_context(console, browser, auth_json_path):
    try:
        context = browser.new_context(storage_state=auth_json_path)
        return context
    except FileNotFoundError:
        console.print("[red]Task file not found or no authentication. Please login first using the 'login' command.[/red]")
        browser.close()
        return None

def _get_valid_entries(console, file_path, browser, date_from=None, date_to=None):
    try:
        entries = read_tasklog(file_path)
    except FileNotFoundError:
        console.print("[red]Auth info file not found. Please login first using the 'login' command.[/red]")
        browser.close()
        return None

    # Filter by date range if provided
    if date_from or date_to:
        if date_from is None:
            date_from_dt = datetime.datetime.min
        else:
            date_from_dt = datetime.datetime.combine(date_from, datetime.time.min)
        if date_to is None:
            date_to_dt = datetime.datetime.max
        else:
            date_to_dt = datetime.datetime.combine(date_to, datetime.time.max)
        entries = [
            entry for entry in entries
            if date_from_dt <= entry.finish <= date_to_dt
        ]

    # Skip tasks with duration 0 or ending with **
    entries = [
        entry for entry in entries
        if entry.duration.total_seconds() > 0 and not entry.task.endswith("**")
    ]
    return entries

def _login_to_timecards(console, page):
    timecards_link = get_timecards_link()
    page.goto(timecards_link)
    console.print(f"[cyan]Waiting for login at {timecards_link}...[/cyan]")
    page.wait_for_url(timecards_link, timeout=30000)
    return True

def _submit_entries_with_progress(console, page, timecards, interactive, dry_run):
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

    PROGRESS_WIDTH = 30  # Constant for progress description width

    with Progress(
        TextColumn("{task.fields[desc]}", justify="left", style="white"),
        BarColumn(bar_width=PROGRESS_WIDTH+10),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[cyan]{task.fields[count]}", justify="right"),
        "•",
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        total = len(timecards)
        task = progress.add_task(
            "Submitting entries", total=total, desc="Submitting entries".ljust(PROGRESS_WIDTH), count=f"0/{total}"
        )
        for idx, timecard in enumerate(timecards, 1):
            if not dry_run:
                _submit_single_entry(page, timecard, interactive)
            else:
                time.sleep(0.2)
            desc = timecard.desc
            desc = (desc[:PROGRESS_WIDTH-3] + "...") if len(desc) > PROGRESS_WIDTH else desc.ljust(PROGRESS_WIDTH)
            progress.update(task, advance=1, desc=desc, count=f"{idx}/{total}")
        progress.update(task, completed=total, count=f"{total}/{total}")

def _submit_single_entry(page, timecard_entry, interactive):
    _fill_owner(page, timecard_entry.owner)

    _fill_case_number(page, timecard_entry.case_no)

    _fill_description(page, timecard_entry.work_performed)
    _fill_duration(page, str(timecard_entry.minutes))

    date = timecard_entry.start_date.strftime("%d/%m/%Y")
    _fill_date(page, date)
    time_str = timecard_entry.start_time.strftime("%H:%M")
    _fill_time(page, time_str)

    if not interactive:
        page.locator('xpath=//lightning-button[button[@name="SaveAndNew"]]').click()

def _cancel_edit(page):
    page.locator('xpath=//lightning-button[button[@name="CancelEdit"]]').click()

def _fill_owner(page, value):
    placeholder = "Search People..."
    xpath = f'xpath=//lightning-base-combobox-formatted-text[@title="{value}"]'
    select_from_combo(page, value, placeholder, xpath)

def _fill_case_number(page, value):
    placeholder = "Search Cases..."
    xpath = f'xpath=//lightning-base-combobox-formatted-text[@title="{value}"]'
    select_from_combo(page, value, placeholder, xpath)

def _fill_description(page, value):
    xpath = f"xpath=//textarea[@maxlength='255']"
    page.locator(xpath).fill(value)

def _fill_duration(page, value):
    xpath = f"xpath=//input[@name='TotalMinutesStatic__c']"
    page.locator(xpath).fill(value)

def _fill_date(page, value):
    xpath = "xpath=//input[@name='StartTime__c' and not(@role='combobox')]"
    page.locator(xpath).fill(value)

def _fill_time(page, value):
    xpath = "xpath=//input[@name='StartTime__c' and @role='combobox']"
    page.locator(xpath).fill(value)