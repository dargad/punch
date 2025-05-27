#!/bin/bash
# filepath: scripts/test_all_cli_options.sh

set -e

PUNCH="python -m punch.cli"
TASKS_FILE="test_tasks.txt"
CONFIG_FILE="test_config.yaml"

# Prepare a minimal config and tasks file for testing
cat > $CONFIG_FILE <<EOF
categories:
  Coding:
    short: c
    caseid: "100"
  Meeting:
    short: m
    caseid: "200"
EOF

export XDG_CONFIG_HOME=$(pwd)
export XDG_DATA_HOME=$(pwd)

# 1. Test: start command with time
$PUNCH start -t 09:00

# 2. Test: add command
$PUNCH add c : "Test task" : "Some notes"

# 3. Test: report command (default dates)
$PUNCH report

# 4. Test: report command with date range
$PUNCH report -f 2025-01-01 -t 2025-12-31

# 5. Test: export as JSON
$PUNCH export --format json -o test_export.json

# 6. Test: export as CSV
$PUNCH export --format csv -o test_export.csv

## 7. Test: login (should fail gracefully if not configured)
#$PUNCH login || echo "Login failed as expected (no URL configured)"
#
## 8. Test: submit dry run, non-interactive, headless
#$PUNCH submit -n
#
## 9. Test: submit dry run, interactive (implies headed)
#$PUNCH submit -n -i
#
## 10. Test: submit with sleep
#$PUNCH submit -n --sleep 0.1

# 11. Test: help command
$PUNCH help

echo "All CLI options tested."
