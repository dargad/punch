# punch

**punch** is a command-line tool for tracking, reporting, and submitting your daily work tasks and timecards. It is designed for fast, keyboard-driven workflows and integrates with Salesforce Lightning for timecard submission.

---

## Features

- **Quick task logging** with category, task name, and optional notes
- **Interactive mode** for guided or rapid task entry
- **Rich reporting** with summaries and custom date ranges
- **Export** to CSV or JSON
- **Salesforce Lightning timecard submission** (via Playwright automation)
- **YAML-based configuration** for categories, file locations, and user info
- **Simple text file storage** for version control and backup
- **Bash and Zsh tab completion** for categories, task names, and subcommands

---

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/punch.git
    cd punch
    ```

2. Install dependencies (recommended: use a virtual environment):
    ```sh
    pip install -r requirements.txt
    ```

3. (Optional) Install Playwright browsers:
    ```sh
    playwright install
    ```

---

## Configuration

Punch uses YAML for configuration.

- **Config file:** `$XDG_CONFIG_HOME/punch/punch.yaml` (default: `~/.config/punch/punch.yaml`)
- **Task log:** `$XDG_DATA_HOME/punch/tasks.txt` (default: `~/.local/share/punch/tasks.txt`)

### Example `punch.yaml`

```yaml
full_name: Dariusz Gadomski
timecards_url: <URL for submitting your timecards>

categories:
  Coding:
    short: c
    caseid: "100"
  Meeting:
    short: m
    caseid: "200"
  Bugfix:
    short: b
    caseid: "300"
  Research:
    short: r
    caseid: "400"
```

---

## Usage

### Quick Task Entry (One-liner)

```sh
python punch.py c : "Implement feature X" : "Initial commit"
```

- `c` is the short code for "Coding"
- First colon separates category and task
- Second colon (optional) adds notes

### Interactive Mode

```sh
python punch.py
```

Guided input for category, task name, and notes.

### Subcommands

- `start [-t HH:MM]`  
  Mark the start of your workday.  
  The `-t/--time` argument now accepts only a time (not a full datetime), e.g. `-t 09:00`.

- `add <category> : <task> [: <notes>]`  
  Add a new task with optional notes.

- `report [-f YYYY-MM-DD] [-t YYYY-MM-DD]`  
  Print a report of your timecards for a date range.

- `export [-f YYYY-MM-DD] [-t YYYY-MM-DD] [--format csv|json] [-o FILE]`  
  Export your timecards to CSV or JSON.

- `login`  
  Login to your timecards account (required before submitting).

- `submit [-f YYYY-MM-DD] [-t YYYY-MM-DD] [-n|--dry-run] [--headed] [-i|--interactive] [--sleep SECONDS]`  
  Submit your timecards for a date range.  
  - `-n/--dry-run`: Perform a dry run (no actual submission; confirmation prompts and messages will indicate dry run mode).
  - `-i/--interactive`: Run in interactive mode (implies `--headed`).
  - `--headed`: Run the browser in headed mode.
  - `--sleep`: Sleep for X seconds after filling out the form.

  **Note:** If you use `-i/--interactive`, `--headed` will be automatically set to `True`.

---

## Task Log Format

Tasks are stored in a plain text file:

```
YYYY-MM-DD HH:MM | Category | Task | Notes
```

- The first entry of the day marks the start (zero duration)
- Each following entry defines the end time of the previous task

Example:
```
2025-05-16 09:00 | start | 
2025-05-16 10:00 | Coding | Feature | Implemented feature
```

---

## Shell Completion

- **Bash:** Use `punch-completion.bash` for autocompletion.
- **Zsh:** Use `zsh-completion` for smart completion.

---

## Development & Testing

Run all tests:

```sh
python -m unittest discover -s tests
```

Run a specific test:

```sh
python -m unittest tests/test_tasks.py
```

---

## Tips

- Tasks ending with `**` or with duration `0` are **not submitted**.
- Salesforce case numbers are padded to 8 digits from config.
- Always `login` before submitting to ensure session is active.
- When submitting, you will see a table of timecards and be prompted to confirm submission. If `--dry-run` is used, confirmation and success messages will indicate dry run mode.

---

## License

MIT License

---

## Author

Dariusz Gadomski

---

*Contributions and feedback are welcome!*