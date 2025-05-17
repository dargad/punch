# punch

**punch** is a simple command-line tool for tracking your daily work tasks and generating time reports. It is designed for developers and teams who want a lightweight, text-based way to log activities, categorize work, and export or report on time spent.

## Features

- **Log tasks** with categories, task names, and optional notes
- **Interactive mode** for quick entry of tasks
- **Report** command to summarize time spent per task and category
- **Export** tasks to CSV or JSON
- **Configurable** categories and task file location
- **Simple text file storage** for easy backup and versioning

## Installation

Clone the repository:

```sh
git clone https://github.com/yourusername/punch.git
cd punch
```

Install dependencies (recommended: use a virtual environment):

```sh
pip install -r requirements.txt
```

## Usage

### Logging a Task (Interactive Mode)

```sh
python punch.py
```

Follow the prompts to select a category and task, or enter a new one.

### Add a New Day Start

```sh
python punch.py new
```
Adds a new entry with task name "new" and no category or notes.

### Generate a Report

```sh
python punch.py report
```
Shows a summary of today's tasks, grouped by category and task.

#### Custom Date Range

```sh
python punch.py report --from 2025-05-01 --to 2025-05-16
```

### Export Tasks

```sh
python punch.py export --format csv --output mytasks.csv
```

## Configuration

Edit your config file (e.g., `config.yaml`) to set categories and task file location:

```yaml
tasks_file: tasks.txt
categories:
  Coding: []
  Meeting: []
  Bugfix: []
  Research: []
```

## Task File Format

Each line in the task file looks like:

```
YYYY-MM-DD HH:MM | Category | Task | Notes
```

The timestamp marks the **finish** of a task. The duration is calculated as the time from the previous entry to this timestamp.

## Running Tests

```sh
python -m unittest discover -s tests
```

## License

MIT License

---

*punch is a work in progress. Contributions and feedback are welcome!*