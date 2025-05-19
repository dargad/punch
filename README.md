# punch

**punch** is a command-line tool for tracking, reporting, and submitting your work tasks and timecards. It is designed for fast keyboard-driven workflows, supports quick task entry, and integrates with Salesforce Lightning for timecard submission.

---

## Features

- **Quick task logging** with category, task name, and optional notes
- **Interactive mode** for guided task entry
- **Rich reporting** with summaries and totals
- **Export** to CSV or JSON
- **Salesforce Lightning timecard submission** (with Playwright automation)
- **Configurable categories** and user info via YAML
- **Bash and Zsh completion** (including quick task entry and task name suggestions)

---

## Installation

1. Clone the repository:
    ```sh
    git clone <repo-url>
    cd punch
    ```

2. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

3. (Optional) Install Playwright browsers:
    ```sh
    playwright install
    ```

---

## Configuration

Punch uses YAML for configuration, stored at:

- **Config:** `$XDG_CONFIG_HOME/punch/punch.yaml` (default: `~/.config/punch/punch.yaml`)
- **Tasks:** `$XDG_DATA_HOME/punch/tasks.txt` (default: `~/.local/share/punch/tasks.txt`)

### Example `punch.yaml`

```yaml
full_name: Dariusz Gadomski

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

- `full_name`: Your name (used for timecard submission)
- `categories`: Mapping of category names to short codes and Salesforce case IDs

---

## Usage

### Quick Task Entry

Log a task in one line:

```sh
python punch.py c : "Implement feature X" : "Initial commit"
```

- `c` is the short code for "Coding"
- The first colon separates category and task
- The second colon (optional) separates task and notes

### Interactive Mode

Just run:

```sh
python punch.py
```

You'll be prompted to select a category, task, and enter notes.

### Subcommands

```sh
python punch.py <subcommand> [options]
```

#### `start`
Mark the start of your day.

```sh
python punch.py start
```

#### `report`
Print a report of your timecards.

```sh
python punch.py report -f 2025-05-01 -t 2025-05-18
```

#### `export`
Export your timecards to CSV or JSON.

```sh
python punch.py export --format csv -f 2025-05-01 -t 2025-05-18 -o my_report.csv
```

#### `login`
Open a browser and log in to Salesforce Lightning. Saves authentication for later submissions.

```sh
python punch.py login
```

#### `submit`
Submit your timecards to Salesforce Lightning.

```sh
python punch.py submit --headed
```

---

## Task Log Format

Tasks are stored in `tasks.txt` as lines like:

```
2025-05-16 09:00 | start | 
2025-05-16 10:00 | Coding | Feature | Implemented feature
```

- Format: `YYYY-MM-DD HH:MM | Category | Task | Notes`
- The first task of each day has duration 0; subsequent tasks have duration relative to the previous task.

---

## Bash & Zsh Completion

- **Bash:** See [`punch-completion.bash`](#) for tab completion of subcommands, categories, and task names.
- **Zsh:** See [`_punch.py`](#) for zsh completion with the same features.

---

## Development & Testing

Run all tests:

```sh
python -m unittest discover -s tests
```

Or a specific test:

```sh
python -m unittest tests/test_tasks.py
```

---

## License

MIT

---

## Author

Dariusz Gadomski

---

## Tips

- Tasks ending with `**` or with duration 0 are skipped for submission.
- Case numbers are matched from the config file and left-filled to 8 digits.
- For Salesforce submission, ensure your config and authentication are set up (`login` first).

---