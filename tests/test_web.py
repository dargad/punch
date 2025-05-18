import unittest
import tempfile
import os
from punch.web import determine_case_number
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

    def tearDown(self):
        self.config_dir.cleanup()

    def test_case_number_found(self):
        entry = SimpleNamespace(category="Meeting")
        self.assertEqual(determine_case_number(entry), "00000200")
        entry = SimpleNamespace(category="Bugfix")
        self.assertEqual(determine_case_number(entry), "00000300")

    def test_case_number_not_found(self):
        entry = SimpleNamespace(category="Nonexistent")
        self.assertIsNone(determine_case_number(entry))

    def test_case_number_missing_caseid(self):
        # Remove caseid from Research
        import yaml
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)
        config["categories"]["Research"].pop("caseid")
        with open(self.config_path, "w") as f:
            yaml.safe_dump(config, f)
        entry = SimpleNamespace(category="Research")
        self.assertIsNone(determine_case_number(entry))

    def test_case_number_left_filled(self):
        entry = SimpleNamespace(category="Coding")
        self.assertEqual(determine_case_number(entry), "00000100")

if __name__ == "__main__":
    unittest.main()