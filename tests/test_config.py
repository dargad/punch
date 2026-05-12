import unittest
import os
import tempfile
import shutil
from unittest import mock

from punch.config import load_config, get_config_path, get_config_d_path, _deep_merge


class TestDeepMerge(unittest.TestCase):
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"a": 1, "b": 3, "c": 4})

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 10, "z": 20}}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"a": {"x": 1, "y": 10, "z": 20}, "b": 3})

    def test_override_dict_with_non_dict(self):
        base = {"a": {"x": 1}}
        override = {"a": "string"}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"a": "string"})

    def test_override_non_dict_with_dict(self):
        base = {"a": "string"}
        override = {"a": {"x": 1}}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"a": {"x": 1}})

    def test_empty_base(self):
        base = {}
        override = {"a": 1}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"a": 1})

    def test_empty_override(self):
        base = {"a": 1}
        override = {}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"a": 1})


class TestLoadConfigSingleFile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "punch")
        os.makedirs(self.config_dir)
        self.config_path = os.path.join(self.config_dir, "punch.yaml")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_load_single_config_file(self):
        with open(self.config_path, "w") as f:
            f.write("key1: value1\nkey2: value2\n")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = os.path.join(self.config_dir, "punch.d")
            config = load_config(self.config_path)

        self.assertEqual(config, {"key1": "value1", "key2": "value2"})

    def test_load_empty_config_file(self):
        with open(self.config_path, "w") as f:
            f.write("")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = os.path.join(self.config_dir, "punch.d")
            config = load_config(self.config_path)

        self.assertEqual(config, {})

    def test_load_nested_config(self):
        with open(self.config_path, "w") as f:
            f.write("settings:\n  theme: dark\n  timeout: 30\n")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = os.path.join(self.config_dir, "punch.d")
            config = load_config(self.config_path)

        self.assertEqual(config, {"settings": {"theme": "dark", "timeout": 30}})


class TestLoadConfigFromPunchD(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "punch")
        self.config_d_path = os.path.join(self.config_dir, "punch.d")
        os.makedirs(self.config_d_path)
        self.config_path = os.path.join(self.config_dir, "punch.yaml")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_load_single_file_from_punch_d(self):
        with open(os.path.join(self.config_d_path, "01-base.yaml"), "w") as f:
            f.write("key1: value1\nkey2: value2\n")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = self.config_d_path
            config = load_config(self.config_path)

        self.assertEqual(config, {"key1": "value1", "key2": "value2"})

    def test_load_multiple_files_alphabetically(self):
        with open(os.path.join(self.config_d_path, "01-base.yaml"), "w") as f:
            f.write("key1: value1\nkey2: original\n")
        with open(os.path.join(self.config_d_path, "02-override.yaml"), "w") as f:
            f.write("key2: overridden\nkey3: value3\n")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = self.config_d_path
            config = load_config(self.config_path)

        self.assertEqual(config, {"key1": "value1", "key2": "overridden", "key3": "value3"})

    def test_load_files_deep_merge(self):
        with open(os.path.join(self.config_d_path, "01-base.yaml"), "w") as f:
            f.write("settings:\n  theme: light\n  timeout: 30\n")
        with open(os.path.join(self.config_d_path, "02-override.yaml"), "w") as f:
            f.write("settings:\n  theme: dark\n")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = self.config_d_path
            config = load_config(self.config_path)

        self.assertEqual(config, {"settings": {"theme": "dark", "timeout": 30}})

    def test_ignores_non_yaml_files(self):
        with open(os.path.join(self.config_d_path, "01-base.yaml"), "w") as f:
            f.write("key1: value1\n")
        with open(os.path.join(self.config_d_path, "readme.txt"), "w") as f:
            f.write("This should be ignored\n")
        with open(os.path.join(self.config_d_path, "config.json"), "w") as f:
            f.write('{"key2": "value2"}\n')

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = self.config_d_path
            config = load_config(self.config_path)

        self.assertEqual(config, {"key1": "value1"})

    def test_empty_punch_d_returns_empty_config(self):
        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = self.config_d_path
            config = load_config(self.config_path)

        self.assertEqual(config, {})

    def test_punch_d_takes_precedence_over_punch_yaml(self):
        # Even if punch.yaml exists, punch.d should be used
        with open(self.config_path, "w") as f:
            f.write("from_single_file: true\n")
        with open(os.path.join(self.config_d_path, "01-config.yaml"), "w") as f:
            f.write("from_punch_d: true\n")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = self.config_d_path
            config = load_config(self.config_path)

        self.assertEqual(config, {"from_punch_d": True})
        self.assertNotIn("from_single_file", config)

    def test_alphabetical_order_matters(self):
        # z-file should override a-file
        with open(os.path.join(self.config_d_path, "z-last.yaml"), "w") as f:
            f.write("order: last\n")
        with open(os.path.join(self.config_d_path, "a-first.yaml"), "w") as f:
            f.write("order: first\n")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = self.config_d_path
            config = load_config(self.config_path)

        self.assertEqual(config, {"order": "last"})

    def test_handles_empty_yaml_files(self):
        with open(os.path.join(self.config_d_path, "01-empty.yaml"), "w") as f:
            f.write("")
        with open(os.path.join(self.config_d_path, "02-content.yaml"), "w") as f:
            f.write("key: value\n")

        with mock.patch("punch.config.get_config_d_path") as mock_config_d:
            mock_config_d.return_value = self.config_d_path
            config = load_config(self.config_path)

        self.assertEqual(config, {"key": "value"})


if __name__ == "__main__":
    unittest.main()
