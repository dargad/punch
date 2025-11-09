import unittest
import tempfile
import os
import datetime
from punch.tasks import TaskEntry, escape_separators, read_tasklog, parse_task, SEPARATOR, parse_new_task_string

CATEGORIES = {
    "Coding": {"short": "c", "caseid": "100"},
    "Meeting": {"short": "m", "caseid": "200"},
    "Bugfix": {"short": "b", "caseid": "300"},
    "Research": {"short": "r", "caseid": "400"},
}

class TestTasks(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.testfile = tempfile.NamedTemporaryFile(delete=False, mode='w+', encoding='utf-8')
        self.testfile.close()

    def tearDown(self):
        os.unlink(self.testfile.name)

    def test_parse_task_first_entry(self):
        # First entry should have duration 0
        line = "2025-05-16 09:00 | Coding | new | "
        entry = parse_task(line)
        self.assertEqual(entry.finish, datetime.datetime(2025, 5, 16, 9, 0))
        self.assertEqual(entry.category, "Coding")
        self.assertEqual(entry.task, "new")
        self.assertEqual(entry.notes, "")
        self.assertEqual(entry.duration, datetime.timedelta(0))

    def test_parse_task_with_previous(self):
        # Second entry should have duration from previous finish
        prev = TaskEntry(
            finish=datetime.datetime(2025, 5, 16, 9, 0),
            category="Coding",
            task="new",
            notes="",
            duration=datetime.timedelta(0)
        )
        line = "2025-05-16 10:00 | Coding | Feature | Implemented feature"
        # Simulate read_tasklog logic for duration
        entry = parse_task(line)
        entry = TaskEntry(entry.finish, entry.category, entry.task, entry.notes, entry.finish - prev.finish)
        self.assertEqual(entry.finish, datetime.datetime(2025, 5, 16, 10, 0))
        self.assertEqual(entry.duration, datetime.timedelta(hours=1))

    def test_read_tasklog(self):
        # Write two entries to the file
        lines = [
            "2025-05-16 09:00 | Coding | new | \n",
            "2025-05-16 10:00 | Coding | Feature | Implemented feature\n"
        ]
        with open(self.testfile.name, 'w') as f:
            f.writelines(lines)
        tasklog = read_tasklog(self.testfile.name)
        self.assertEqual(len(tasklog), 1)  # Only the second entry has duration > 0
        self.assertEqual(tasklog[0].finish, datetime.datetime(2025, 5, 16, 10, 0))
        self.assertEqual(tasklog[0].duration, datetime.timedelta(hours=1))

    def test_chronological_order(self):
        # Should not raise, but duration will be negative if out of order
        prev = TaskEntry(
            finish=datetime.datetime(2025, 5, 16, 10, 0),
            category="Coding",
            task="Feature",
            notes="",
            duration=datetime.timedelta(hours=1)
        )
        line = "2025-05-16 09:00 | Coding | Bugfix | Fixed bug"
        entry = parse_task(line)
        duration = entry.finish - prev.finish
        self.assertTrue(isinstance(duration, datetime.timedelta))

    def test_parse_task_invalid_format(self):
        # Should raise if the line is not in the expected format
        with self.assertRaises(Exception):
            parse_task("not a valid task line")

    def test_parse_new_task_string_invalid_category(self):
        # Should raise if category short code is not found
        with self.assertRaises(ValueError):
            parse_new_task_string("x : Task", CATEGORIES)

    def test_parse_new_task_string_empty(self):
        # Should raise ValueError for empty input
        with self.assertRaises(ValueError):
            parse_new_task_string("", CATEGORIES)

    def test_escape_separators(self):
        self.assertEqual(escape_separators("foo:bar"), "foo\\:bar")
        self.assertEqual(escape_separators(":bar"), ":bar")
        self.assertEqual(escape_separators("foo:"), "foo:")
        self.assertEqual(escape_separators("a:b:c"), "a\\:b\\:c")

    def test_task_entry_repr(self):
        entry = TaskEntry(
            finish=datetime.datetime(2025, 5, 16, 10, 0),
            category="Coding",
            task="Feature",
            notes="Test",
            duration=datetime.timedelta(hours=1)
        )
        self.assertIn("Coding", repr(entry))
        self.assertIn("Feature", repr(entry))

# Typer-based CLI tests (basic smoke test using subprocess)
import subprocess

class TestTyperCLI(unittest.TestCase):
    def test_report_help(self):
        result = subprocess.run(
            ["python", "-m", "punch.ui.cli", "report", "--help"],
            capture_output=True, text=True
        )
        self.assertIn("Usage", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_start_help(self):
        result = subprocess.run(
            ["python", "-m", "punch.ui.cli", "start", "--help"],
            capture_output=True, text=True
        )
        self.assertIn("Usage", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_config_show_help(self):
        result = subprocess.run(
            ["python", "-m", "punch.ui.cli", "config", "show", "--help"],
            capture_output=True, text=True
        )
        self.assertIn("Usage", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_cli_global_help(self):
        result = subprocess.run(
            ["python", "-m", "punch.ui.cli", "--help"],
            capture_output=True, text=True
        )
        self.assertIn("Usage", result.stdout)
        self.assertEqual(result.returncode, 0)