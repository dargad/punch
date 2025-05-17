import unittest
import tempfile
import os
import datetime
from punch.tasks import TaskEntry, read_tasklog, parse_task, SEPARATOR

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
        tasklog = []
        entry = parse_task(line, tasklog)
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
        tasklog = [prev]
        entry = parse_task(line, tasklog)
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
        # Patch tasks.txt to our temp file
        orig_open = open
        def fake_open(filename, *args, **kwargs):
            if filename == 'tasks.txt':
                return orig_open(self.testfile.name, *args, **kwargs)
            return orig_open(filename, *args, **kwargs)
        import builtins
        builtins_open = builtins.open
        builtins.open = fake_open
        try:
            tasklog = read_tasklog('tasks.txt')
            self.assertEqual(len(tasklog), 2)
            self.assertEqual(tasklog[0].finish, datetime.datetime(2025, 5, 16, 9, 0))
            self.assertEqual(tasklog[1].duration, datetime.timedelta(hours=1))
        finally:
            builtins.open = builtins_open

    def test_chronological_order(self):
        # Should raise ValueError if entries are not in order
        prev = TaskEntry(
            finish=datetime.datetime(2025, 5, 16, 10, 0),
            category="Coding",
            task="Feature",
            notes="",
            duration=datetime.timedelta(hours=1)
        )
        line = "2025-05-16 09:00 | Coding | Bugfix | Fixed bug"
        tasklog = [prev]
        with self.assertRaises(ValueError):
            parse_task(line, tasklog)

if __name__ == "__main__":
    unittest.main()