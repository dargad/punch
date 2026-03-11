import os
import yaml

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None

def get_config_path():
    # Use ~/.config which works in both snap (HOME is remapped) and non-snap environments
    config_dir = os.path.join(os.path.expanduser("~/.config"), "punch")
    return os.path.join(config_dir, "punch.yaml")

def get_tasks_file():
    # Use ~/.local/share which works in both snap (HOME is remapped) and non-snap environments
    data_dir = os.path.join(os.path.expanduser("~/.local/share"), "punch")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "tasks.txt")

def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}
    
def set_config_value(config, config_path, key, value):
    """
    Set a config value, preserving whitespace and comments in the YAML file.
    Requires ruamel.yaml.
    """
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if YAML is None:
        raise ImportError("ruamel.yaml is required to preserve comments and formatting.")
    yaml_ruamel = YAML()
    yaml_ruamel.preserve_quotes = True
    # Load the original YAML preserving formatting
    with open(config_path, "r") as f:
        data = yaml_ruamel.load(f)
    data[key] = value
    with open(config_path, "w") as f:
        yaml_ruamel.dump(data, f)