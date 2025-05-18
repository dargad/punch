import os
from playwright.sync_api import sync_playwright
from punch.tasks import read_tasklog
from datetime import datetime
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.console import Console
import time

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

def submit_timecards(file_path="tasks.txt", headless=True):
    PROGRESS_WIDTH = 30  # Constant for progress description width

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
                time.sleep(1)
                desc = f"{entry.task}"
                # Pad or truncate to PROGRESS_WIDTH chars
                desc = (desc[:PROGRESS_WIDTH-3] + "...") if len(desc) > PROGRESS_WIDTH else desc.ljust(PROGRESS_WIDTH)
                progress.update(task, advance=1, desc=desc, count=f"{idx}/{total}")
            progress.update(task, completed=total, count=f"{total}/{total}")

        console.print(f"[bold green]Submitted {len(entries)} entries.[/bold green]")
        browser.close()
