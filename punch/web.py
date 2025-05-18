import os
from playwright.sync_api import sync_playwright
from punch.tasks import read_tasklog
from datetime import datetime
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.console import Console
import time
import re

TIMECARDS_LINK = "https://canonical.lightning.force.com/lightning/o/TimeCard__c/new"

def log_redirects(request):
    from rich.console import Console
    console = Console()
    if request.redirected_from:
        console.print(
            f"[yellow]Redirected from[/yellow] [cyan]{request.redirected_from.url}[/cyan] [yellow]to[/yellow] [cyan]{request.url}[/cyan]"
        )

def login_to_site():
    console = Console()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        if os.path.exists("auth.json"):
            context = browser.new_context(storage_state="auth.json")
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

        context.storage_state(path="auth.json")
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
    return "00255865"

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

def submit_timecards(file_path="tasks.txt", headless=True):
    PROGRESS_WIDTH = 30  # Constant for progress description width

    console = Console()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            context = browser.new_context(storage_state="auth.json")
        except FileNotFoundError:
            console.print("[red]Task file not found or no authentication. Please login first using the 'login' command.[/red]")
            browser.close()
            return

        try:
            entries = read_tasklog(file_path)
        except FileNotFoundError:
            console.print("[red]Auth info file not found. Please login first using the 'login' command.[/red]")
            browser.close()
            return

        # Skip tasks with duration 0 or ending with **
        entries = [
            entry for entry in entries
            if entry.duration.total_seconds() > 0 and not entry.task.endswith("**")
        ]
        if not entries:
            console.print("[yellow]No tasks to submit.[/yellow]")
            browser.close()
            return

        page = context.new_page()
        page.goto(TIMECARDS_LINK)
        console.print(f"[cyan]Waiting for login at {TIMECARDS_LINK}...[/cyan]")
        page.wait_for_url(TIMECARDS_LINK, timeout=30000)
        console.print("[green]Login successful. Submitting timecards...[/green]")

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
                
                full_name = entry.category

                case_no = determine_case_number(entry)

                fill_case_number(page, case_no)

                fill_owner(page, "Dariusz Gadomski")

                if not case_no:
                    # if no case number mapping found try to extract it from the task
                    case_no = extract_case_number(entry.task)
                    desc = entry.desc
                else:
                    # if mapping has been found use taskname as notes
                    desc = entry.task

                fill_description(page, desc)

                duration = int(entry.duration.total_seconds() // 60)
                fill_duration(page, str(duration))
                
                date = entry.finish.strftime("%d/%m/%Y")
                fill_date(page, date)

                time = entry.finish.strftime("%H:%M")
                fill_time(page, time)

                page.locator('xpath=//lightning-button[button[@name="SaveAndNew"]]').click()
                input("Press Enter to continue...")

                progress.update(task, advance=1, desc=desc, count=f"{idx}/{total}")
            progress.update(task, completed=total, count=f"{total}/{total}")

        page.locator('xpath=//lightning-button[button[@name="CancelEdit"]]').click()

        console.print(f"[bold green]Submitted {len(entries)} entries.[/bold green]")
        browser.close()

def fill_owner(page, value):
    placeholder = "Search People..."
    xpath = f'xpath=//lightning-base-combobox-formatted-text[@title="{value}"]'
    select_from_combo(page, value, placeholder, xpath)
    print("after select_from_combo")

def fill_case_number(page, value):
    placeholder = "Search Cases..."
    xpath = f'xpath=//lightning-base-combobox-formatted-text[@title="{value}"]'
    select_from_combo(page, value, placeholder, xpath)

def fill_description(page, value):
    xpath = f"xpath=//textarea[@maxlength='255']"
    page.locator(xpath).fill(value)

def fill_duration(page, value):
    xpath = f"xpath=//input[@name='TotalMinutesStatic__c']"
    page.locator(xpath).fill(value)

def fill_date(page, value):
    xpath="xpath=//input[@name='StartTime__c' and not(@role='combobox')]"
    page.locator(xpath).fill(value)

def fill_time(page, value):
    value = "15:09"