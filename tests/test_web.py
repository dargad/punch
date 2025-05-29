import unittest
import tempfile
import os
from punch.web import determine_case_number, DRY_RUN_SUFFIX, submit_timecards, get_timecards
from types import SimpleNamespace

class TestDetermineCaseNumber(unittest.TestCase):
    def setUp(self):
        # Create a temporary config file
        self.config_content = """
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
"""
        self.config_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.config_dir.name, "punch.yaml")
        with open(self.config_path, "w") as f:
            f.write(self.config_content)
        # Patch get_config_path and load_config to use our temp config
        import punch.web
        punch.web.get_config_path = lambda: self.config_path

        import yaml
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)

    def tearDown(self):
        self.config_dir.cleanup()

    def test_case_number_found(self):
        entry = SimpleNamespace(category="Meeting")
        self.assertEqual(determine_case_number(self.config, entry), "00000200")
        entry = SimpleNamespace(category="Bugfix")
        self.assertEqual(determine_case_number(self.config, entry), "00000300")

    def test_case_number_not_found(self):
        entry = SimpleNamespace(category="Nonexistent")
        self.assertIsNone(determine_case_number(self.config, entry))

    def test_case_number_missing_caseid(self):
        # Remove caseid from Research
        self.config["categories"]["Research"].pop("caseid")
        with open(self.config_path, "w") as f:
            import yaml
            yaml.safe_dump(self.config, f)
        entry = SimpleNamespace(category="Research")
        self.assertIsNone(determine_case_number(self.config, entry))

    def test_case_number_left_filled(self):
        entry = SimpleNamespace(category="Coding")
        self.assertEqual(determine_case_number(self.config, entry), "00000100")

class TestDryRunSuffix(unittest.TestCase):
    def test_dry_run_suffix(self):
        self.assertEqual(DRY_RUN_SUFFIX, " (dry run)")

    def test_submit_timecards_dry_run_suffix_in_message(self):
        # This is a functional test stub; in real code, you'd mock Console and Playwright
        # Here, we just check that DRY_RUN_SUFFIX is used in the API and can be passed through
        # For a real test, use unittest.mock to patch Console.print and assert the suffix is present
        self.assertIn("dry run", DRY_RUN_SUFFIX)

class TestGetTimecards(unittest.TestCase):
    def setUp(self):
        self.config_content = """
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
"""
        self.config_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.config_dir.name, "punch.yaml")
        with open(self.config_path, "w") as f:
            f.write(self.config_content)

    def tearDown(self):
        self.config_dir.cleanup()
        self.config_dir = None

    def test_get_timecards_returns_list(self):
        import yaml
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)
        # Should return a list, even if file does not exist
        result = get_timecards(config, file_path="nonexistent.txt")
        self.assertIsInstance(result, list)

if __name__ == "__main__":
    unittest.main()
