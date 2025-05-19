import os
from playwright.sync_api import sync_playwright
from punch.tasks import read_tasklog
from datetime import datetime, time
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.console import Console
import re
from punch.config import get_config_path, load_config

TIMECARDS_LINK = "https://canonical.lightning.force.com/lightning/o/TimeCard__c/new"

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

def login_to_site():
    console = Console()
    auth_json_path = get_auth_json_path()
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False)
        if os.path.exists(auth_json_path):
            context = browser.new_context(storage_state=auth_json_path)
            console.print("[cyan]Loaded existing authentication from auth.json[/cyan]")
        else:
            context = browser.new_context()
            console.print("[yellow]No auth.json found, starting fresh browser session[/yellow]")
        page = context.new_page()
        page.on("request", log_redirects)

        console.print(f"[cyan]Opening login page: {TIMECARDS_LINK}[/cyan]")
        page.goto(TIMECARDS_LINK)

        console.print(f"[cyan]Waiting for login at {TIMECARDS_LINK}...[/cyan]")
        page.wait_for_url(TIMECARDS_LINK, timeout=30000)
        console.print("[green]Login successful.[/green]")

        context.storage_state(path=auth_json_path)
        console.print("[green]Login saved to auth.json[/green]")

        browser.close()

def select_from_combo(page, value, placeholder, xpath):
    """
    Select an item from a Lightning combobox by filling the input, clicking, and selecting the matching element.
    """
    input_box = page.locator(f'input[placeholder="{placeholder}"]')
    print("Input box found:", input_box)
    input_box.fill(f"{value}")
    time.sleep(1)
    input_box.click()
    element = page.locator(xpath)
    print("Element found:", element)
    element.wait_for(state="visible", timeout=10000)
    
    element.click()

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

def submit_timecards(file_path="tasks.txt", headless=True, date_from=None, date_to=None):
    """
    Submits timecards for tasks between date_from and date_to (inclusive).
    date_from and date_to should be datetime.date objects or None (defaults to all).
    """
    PROGRESS_WIDTH = 30  # Constant for progress description width

    console = Console()
    auth_json_path = get_auth_json_path()
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=headless)
        context = _get_browser_context(console, browser, auth_json_path)
        if context is None:
            return

        entries = _get_valid_entries(console, file_path, browser, date_from, date_to)
        if not entries:
            return

        page = context.new_page()
        _login_to_timecards(console, page)

        _submit_entries_with_progress(console, page, entries, PROGRESS_WIDTH)

        _cancel_edit(page)
        console.print(f"[bold green]Submitted {len(entries)} entries.[/bold green]")
        browser.close()

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
            date_from_dt = datetime.min
        else:
            date_from_dt = datetime.combine(date_from, time.min)
        if date_to is None:
            date_to_dt = datetime.max
        else:
            date_to_dt = datetime.combine(date_to, time.max)
        entries = [
            entry for entry in entries
            if date_from_dt <= entry.finish <= date_to_dt
        ]

    # Skip tasks with duration 0 or ending with **
    entries = [
        entry for entry in entries
        if entry.duration.total_seconds() > 0 and not entry.task.endswith("**")
    ]
    if not entries:
        console.print("[yellow]No tasks to submit.[/yellow]")
        browser.close()
        return None
    return entries

def _login_to_timecards(console, page):
    page.goto(TIMECARDS_LINK)
    console.print(f"[cyan]Waiting for login at {TIMECARDS_LINK}...[/cyan]")
    page.wait_for_url(TIMECARDS_LINK, timeout=30000)
    console.print("[green]Login successful. Submitting timecards...[/green]")

def _submit_entries_with_progress(console, page, entries, PROGRESS_WIDTH):
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

    with Progress(
        TextColumn("{task.fields[desc]}", justify="left", style="white"),
        BarColumn(bar_width=PROGRESS_WIDTH+10),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[cyan]{task.fields[count]}", justify="right"),
        "•",
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        total = len(entries)
        task = progress.add_task(
            "Submitting entries", total=total, desc="Submitting entries".ljust(PROGRESS_WIDTH), count=f"0/{total}"
        )
        for idx, entry in enumerate(entries, 1):
            _submit_single_entry(page, entry)
            desc = entry.task
            desc = (desc[:PROGRESS_WIDTH-3] + "...") if len(desc) > PROGRESS_WIDTH else desc.ljust(PROGRESS_WIDTH)
            progress.update(task, advance=1, desc=desc, count=f"{idx}/{total}")
        progress.update(task, completed=total, count=f"{total}/{total}")

def _submit_single_entry(page, entry):
    case_no = determine_case_number(entry)
    _fill_case_number(page, case_no)

    # Fetch full name from config
    config_path = get_config_path()
    config = load_config(config_path)
    full_name = config.get("full_name")
    if not full_name:
        raise Exception("Full name not set in config file. Please add 'full_name' to your config.")

    _fill_owner(page, full_name)

    if not case_no:
        # if no case number mapping found try to extract it from the task
        case_no = extract_case_number(entry.task)
        desc = entry.desc if hasattr(entry, "desc") else entry.task
    else:
        # if mapping has been found use taskname as notes
        desc = entry.task

    _fill_description(page, desc)
    duration = int(entry.duration.total_seconds() // 60)
    _fill_duration(page, str(duration))
    date = entry.finish.strftime("%d/%m/%Y")
    _fill_date(page, date)
    time_str = entry.finish.strftime("%H:%M")
    _fill_time(page, time_str)
    page.locator('xpath=//lightning-button[button[@name="SaveAndNew"]]').click()

def _cancel_edit(page):
    page.locator('xpath=//lightning-button[button[@name="CancelEdit"]]').click()

def _fill_owner(page, value):
    placeholder = "Search People..."
    xpath = f'xpath=//lightning-base-combobox-formatted-text[@title="{value}"]'
    select_from_combo(page, value, placeholder, xpath)
    print("after select_from_combo")

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