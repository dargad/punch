import os
from playwright.sync_api import sync_playwright
from punch.tasks import read_tasklog
from datetime import datetime
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.console import Console
import time

TIMECARDS_LINK = "https://canonical.lightning.force.com/lightning/o/TimeCard__c/new"

def log_redirects(request):
    if request.redirected_from:
        print(f"Redirected from {request.redirected_from.url} to {request.url}")

def login_to_site():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        if os.path.exists("auth.json"):
            context = browser.new_context(storage_state="auth.json")
        else:
            context = browser.new_context()
        page = context.new_page()
        page.on("request", log_redirects)

        page.goto(TIMECARDS_LINK)

        print(f"Waiting for login at {TIMECARDS_LINK}...")
        page.wait_for_url(TIMECARDS_LINK, timeout=30000)
        print("Login successful.")

        context.storage_state(path="auth.json")
        print("Login saved to auth.json")

        browser.close()

def submit_timecards(file_path="tasks.txt", headless=True):
    entries = read_tasklog(file_path)
    # Skip tasks with duration 0 or ending with **
    entries = [
        entry for entry in entries
        if entry.duration.total_seconds() > 0 and not entry.task.endswith("**")
    ]
    if not entries:
        print("No tasks to submit.")
        return

    console = Console()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state="auth.json")
        page = context.new_page()
        page.goto(TIMECARDS_LINK)
        console.print(f"[cyan]Waiting for login at {TIMECARDS_LINK}...[/cyan]")
        page.wait_for_url(TIMECARDS_LINK, timeout=30000)
        console.print("[green]Login successful. Submitting timecards...[/green]")

        with Progress(
            TextColumn("{task.fields[desc]}", justify="left", style="white"),
            BarColumn(bar_width=40),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Submitting entries", total=len(entries), desc="Submitting entries".ljust(40))
            for entry in entries:
                time.sleep(1)
                desc = f"{entry.task}"
                # Pad or truncate to 30 chars
                desc = (desc[:27] + "...") if len(desc) > 30 else desc.ljust(30)
                progress.update(task, advance=1, desc=desc)
            progress.update(task, completed=len(entries))

        console.print(f"[bold green]Submitted {len(entries)} entries.[/bold green]")
        browser.close()
