#!/bin/bash

set -euo pipefail

# Pass an executable path to test a specific installation; default to punch on PATH.
if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [punch-executable]" >&2
    exit 2
fi
PUNCH=${1:-punch}
if ! command -v "$PUNCH" >/dev/null 2>&1; then
    echo "Punch executable not found: $PUNCH" >&2
    exit 1
fi

# A non-hidden directory under HOME is accessible to strictly confined snaps.
test_dir=$(mktemp -d "$HOME/punch-cli-test.XXXXXXXX")
server_pid=
cleanup() {
    if [ -n "$server_pid" ]; then
        kill "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
    rm -rf -- "$test_dir"
}
trap cleanup EXIT
export PUNCH_CONFIG_DIR="$test_dir/config"
export PUNCH_DATA_DIR="$test_dir/data"
export XDG_CONFIG_HOME="$test_dir/xdg"
export PUNCH_NO_NEWS=1
export NO_COLOR=1
mkdir -p "$PUNCH_CONFIG_DIR" "$PUNCH_DATA_DIR" "$XDG_CONFIG_HOME"

cat > "$PUNCH_CONFIG_DIR/punch.yaml" <<'EOF'
full_name: Test User
categories:
  Coding:
    short: c
    caseid: "100"
  Meeting:
    short: m
    caseid: "200"
EOF

assert_contains() {
    if [[ $1 != *"$2"* ]]; then
        printf 'Expected output to contain %s, got:\n%s\n' "$2" "$1" >&2
        exit 1
    fi
}

echo "Testing $PUNCH"
output=$("$PUNCH" --help)
assert_contains "$output" "Usage"
for command in start add report export login submit config weeklyeditor tutorial whats-new; do
    output=$("$PUNCH" "$command" --help)
    assert_contains "$output" "Usage"
done
output=$("$PUNCH" help)
assert_contains "$output" "Usage"

today=$(date +%F)
"$PUNCH" start -t 09:00
output=$("$PUNCH" add -t 10:00 c : "Test task" : "Some notes")
assert_contains "$output" "Task logged"

output=$("$PUNCH" report)
assert_contains "$output" "Test task"
assert_contains "$output" "60 min"
output=$("$PUNCH" report -f "$today" -t "$today")
assert_contains "$output" "Test task"
output=$("$PUNCH" report -d yesterday)
if [[ $output == *"Test task"* ]]; then
    echo "Yesterday's report unexpectedly contains today's task" >&2
    exit 1
fi

"$PUNCH" export --format json -o "$test_dir/export.json"
"$PUNCH" export --format csv -o "$test_dir/export.csv"
python3 - "$test_dir" "$today" <<'PY'
import csv
import json
import pathlib
import sys

directory = pathlib.Path(sys.argv[1])
expected = {
    "category": "Coding",
    "task": "Test task",
    "notes": "Some notes",
    "finish": f"{sys.argv[2]}T10:00:00",
    "duration_minutes": 60,
}
with (directory / "export.json").open() as f:
    assert json.load(f) == [expected], "Unexpected JSON export"
with (directory / "export.csv").open(newline="") as f:
    rows = list(csv.DictReader(f))
expected["duration_minutes"] = "60"
assert rows == [expected], "Unexpected CSV export"
PY

output=$("$PUNCH" config show)
assert_contains "$output" "Coding"
output=$("$PUNCH" config path)
assert_contains "$output" "$PUNCH_CONFIG_DIR/punch.yaml"
output=$("$PUNCH" config get categories)
assert_contains "$output" "Coding"
output=$("$PUNCH" config get doesnotexist)
assert_contains "$output" "not found"
"$PUNCH" config set foo bar
output=$("$PUNCH" config get foo)
if [ "$output" != "bar" ]; then
    printf 'Expected config value bar, got: %s\n' "$output" >&2
    exit 1
fi

if output=$("$PUNCH" add unknown : "Test task" 2>&1); then
    echo "Adding an unknown category unexpectedly succeeded" >&2
    exit 1
fi
assert_contains "$output" "not found"

if output=$("$PUNCH" login 2>&1); then
    echo "Login without a timecards URL unexpectedly succeeded" >&2
    exit 1
fi
assert_contains "$output" "No timecards_url"

for options in "-n" "-n --headed" "-n -i" "-n --resume --sleep 0.1"; do
    # These option lists are fixed above; no user input is word-split.
    read -r -a args <<< "$options"
    output=$(printf 'n\n' | "$PUNCH" submit "${args[@]}")
    assert_contains "$output" "Submission cancelled"
done

if [ "${PUNCH_TEST_BROWSER:-0}" = "1" ]; then
    python3 -u - "$test_dir/port" <<'PY' &
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Punch login smoke test")

    def log_message(self, format, *args):
        pass

server = HTTPServer(("127.0.0.1", 0), Handler)
Path(sys.argv[1]).write_text(str(server.server_port))
server.serve_forever()
PY
    server_pid=$!
    for _ in {1..100}; do
        [ -s "$test_dir/port" ] && break
        if ! kill -0 "$server_pid" 2>/dev/null; then
            echo "Local login test server failed to start" >&2
            exit 1
        fi
        sleep 0.1
    done
    if [ ! -s "$test_dir/port" ]; then
        echo "Timed out waiting for local login test server" >&2
        exit 1
    fi
    printf 'timecards_url: http://127.0.0.1:%s/\n' "$(cat "$test_dir/port")" >> "$PUNCH_CONFIG_DIR/punch.yaml"
    if ! output=$(timeout 60 "$PUNCH" login 2>&1); then
        printf 'Browser login smoke test failed:\n%s\n' "$output" >&2
        exit 1
    fi
    assert_contains "$output" "Login saved to auth.json"
    test -s "$PUNCH_CONFIG_DIR/auth.json"
else
    echo "Skipping browser login smoke test (set PUNCH_TEST_BROWSER=1 to enable)."
fi

echo "CLI checks passed. Actual submission and interactive interfaces were not exercised."
