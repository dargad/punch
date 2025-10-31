# Punch CLI

**Punch** is a command-line tool for tracking tasks, generating reports, exporting timecards, and submitting them to Salesforce.  
It uses [Typer](https://typer.tiangolo.com/) for its CLI, supports configuration management, and provides interactive and scriptable workflows.

## Installation

```bash
pip install punch
# or if using poetry
poetry install
```

or

```bash
snap install punch
```

## Usage

### Main Commands

- `punch start [-t HH:MM]`  
  Mark the start of your day. Optionally specify the start time.

- `punch add [-t HH:MM] <category> : <task> [: <notes>]`  
  Add a new task entry. You can specify the time with `-t`.

- `punch report [-d DAY | -f FROM -t TO]`  
  Print a report for a single day (`-d`) or a date range (`-f`/`-t`). Dates accept natural language (e.g. `yesterday`, `2025-01-01`).

- `punch export [options]`  
  Export timecards to CSV or JSON. Supports the same date options as `report`.

- `punch login`  
  Log in to Salesforce and store your session locally.

- `punch submit [options]`  
  Submit timecards to Salesforce. Supports dry-run, interactive/headed mode, and sleep between actions.

- `punch config <subcommand>`  
  Manage configuration. Subcommands:
  - `show` — Show the current configuration.
  - `edit` — Edit the config file in `$EDITOR`.
  - `path` — Show the config file path.
  - `set <option> <value>` — Set a config value.
  - `get <option>` — Get a config value.
  - `wizard` — Run the interactive config wizard.

- `punch help [COMMAND ...]`  
  Show help for the app or any subcommand.

- `punch whats-new`  
  Show the changelog for the current version.

### Interactive Mode

Running `punch` with no arguments launches an interactive prompt for selecting categories and tasks.

### Date Handling

- Dates can be specified as natural language (`yesterday`, `today`, `last monday`) or as `YYYY-MM-DD`.
- For ranges, use `-f`/`--from` and `-t`/`--to`.
- `-d`/`--day` sets both start and end to the same day.

### Configuration

Configuration is stored in a YAML file (see `punch config path`).  
You can edit it directly, use `punch config set/get`, or run `punch config wizard` for guided setup.

### Completion

Bash and Zsh completion scripts are provided in the repo (`punch-completion.bash`, `zsh-completion`).  
Source them in your shell for tab completion of commands and options.

### Examples

```bash
punch start -t 09:00
punch add c : "Implement feature X" : "Initial commit"
punch report -d yesterday
punch export --format csv -f 2025-01-01 -t 2025-01-31 -o jan.csv
punch config show
punch config set timecards_url https://example.com/timecards
punch submit -n -f 2025-01-01 -t 2025-01-31
```

## Development

- All commands are implemented using [Typer](https://typer.tiangolo.com/).
- Tests are in the `tests/` directory and cover both core logic and CLI usage.
- See `punch/cli.py` for the main entrypoint.

## License

MIT

---

For more details, see the [CHANGELOG](CHANGELOG.md) or run `punch whats-new`.

[![Build Snap package](https://github.com/dargad/punch/actions/workflows/build-snap.yml/badge.svg)](https://github.com/dargad/punch/actions/workflows/build-snap.yml)
[![Run Python unit tests](https://github.com/dargad/punch/actions/workflows/python-unittests.yml/badge.svg)](https://github.com/dargad/punch/actions/workflows/python-unittests.yml)
[![Test All CLI Options](https://github.com/dargad/punch/actions/workflows/sanity-check.yml/badge.svg)](https://github.com/dargad/punch/actions/workflows/sanity-check.yml)
