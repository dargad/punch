import unittest
from datetime import date, timedelta
from punch.ui.cli import resolve_date_range
import typer

class TestResolveDateRange(unittest.TestCase):
    def test_day_only(self):
        # Only day provided, from and to should match day
        d = date.today().strftime("%Y-%m-%d")
        day, from_, to_ = resolve_date_range(d, None, None)
        self.assertEqual(day, from_)
        self.assertEqual(day, to_)
        self.assertIsInstance(day, date)

    def test_from_only(self):
        # Only from provided, to should default to today
        f = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        day, from_, to_ = resolve_date_range(None, f, None)
        self.assertIsNone(day)
        self.assertEqual(from_.strftime("%Y-%m-%d"), f"{date.today() - timedelta(days=2)}")
        self.assertEqual(to_, date.today())

    def test_from_and_to(self):
        # Both from and to provided
        f = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        t = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        day, from_, to_ = resolve_date_range(None, f, t)
        self.assertIsNone(day)
        self.assertEqual(from_.strftime("%Y-%m-%d"), f"{date.today() - timedelta(days=5)}")
        self.assertEqual(to_.strftime("%Y-%m-%d"), f"{date.today() - timedelta(days=2)}")

    def test_day_and_from(self):
        # Both day and from provided, should raise
        d = date.today().strftime("%Y-%m-%d")
        f = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        with self.assertRaises(typer.Exit):
            resolve_date_range(d, f, None)

    def test_to_without_from(self):
        # to provided without from, should raise
        t = date.today().strftime("%Y-%m-%d")
        with self.assertRaises(typer.Exit):
            resolve_date_range(None, None, t)

    def test_from_after_to(self):
        # from after to, should raise
        f = date.today().strftime("%Y-%m-%d")
        t = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        with self.assertRaises(typer.Exit):
            resolve_date_range(None, f, t)

    def test_none_all(self):
        # All None, should default to today
        day, from_, to_ = resolve_date_range(None, None, None)
        self.assertEqual(day, date.today())
        self.assertEqual(from_, date.today())
        self.assertEqual(to_, date.today())

if __name__ == "__main__":
    unittest.main()
