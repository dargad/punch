import unittest
import tempfile
import os
import datetime
from punch.tasks import TaskEntry, read_tasklog, parse_task, SEPARATOR, parse_new_task_string

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

CATEGORIES = {
    "Coding": {"short": "c", "caseid": "100"},
    "Meeting": {"short": "m", "caseid": "200"},
    "Bugfix": {"short": "b", "caseid": "300"},
    "Research": {"short": "r", "caseid": "400"},
}

class TestParseNewTaskString(unittest.TestCase):
    def test_parse_new_task_string_categoryless_star(self):
        entry = parse_new_task_string("lunch**", CATEGORIES)
        self.assertEqual(entry.category, "")
        self.assertEqual(entry.task, "lunch**")
        self.assertEqual(entry.notes, "")

    def test_parse_new_task_string_categoryless_double_star(self):
        entry = parse_new_task_string("breakfast**", CATEGORIES)
        self.assertEqual(entry.category, "")
        self.assertEqual(entry.task, "breakfast**")
        self.assertEqual(entry.notes, "")

    def test_parse_new_task_string_with_escaped_colon_in_task(self):
        entry = parse_new_task_string(r'c : Implement foo\:bar : Some notes', CATEGORIES)
        self.assertEqual(entry.category, "Coding")
        self.assertEqual(entry.task, "Implement foo:bar")
        self.assertEqual(entry.notes, "Some notes")

    def test_parse_new_task_string_with_escaped_colon_in_notes(self):
        entry = parse_new_task_string(r'c : Task name : Note with foo\:bar inside', CATEGORIES)
        self.assertEqual(entry.category, "Coding")
        self.assertEqual(entry.task, "Task name")
        self.assertEqual(entry.notes, "Note with foo:bar inside")

    def test_parse_new_task_string_with_multiple_escaped_colons(self):
        entry = parse_new_task_string(r'c : foo\:bar\:baz : note\:with\:colons', CATEGORIES)
        self.assertEqual(entry.category, "Coding")
        self.assertEqual(entry.task, "foo:bar:baz")
        self.assertEqual(entry.notes, "note:with:colons")

if __name__ == "__main__":
    unittest.main()