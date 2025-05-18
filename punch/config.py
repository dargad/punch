import os
import yaml

def get_config_path():
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg_config_home, "punch", "punch.yaml")

def get_tasks_file():
    xdg_data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    data_dir = os.path.join(xdg_data_home, "punch")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "tasks.txt")

def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}